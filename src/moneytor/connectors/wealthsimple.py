"""Wealthsimple connector — UNOFFICIAL API.

Wealthsimple publishes no official/documented API. This connector targets the
community-reverse-engineered flow:

1. Password grant (email + password) against the OAuth v2 login host. If 2FA is
   enabled, the first request is rejected with an OTP challenge (an
   ``x-wealthsimple-otp`` response header); the request is retried with the
   user-supplied code in the ``x-wealthsimple-otp`` request header.
2. The returned refresh token is persisted via :class:`TokenStore` so later runs
   refresh silently (no 2FA prompt) until it expires.
3. The account's ``identity_canonical_id`` is read from the token-info endpoint.
4. Accounts, positions, and balances are read from the **GraphQL** API
   (``my.wealthsimple.com/graphql``) and mapped into normalized domain models.

The OTP code is obtained from an injected ``otp_provider`` callable (a GUI
dialog in the app, ``input()`` in a CLI, or a fixed value in tests).

⚠️ The endpoints, GraphQL queries, and payload shapes below were validated
against the live service, but remain unofficial and may change without notice.
All parsing is defensive and raises ``FetchError`` on mismatch rather than
crashing. Queries are kept minimal (only the fields we map) and centralized so
tuning is a one-file change.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx

from moneytor.config.secret import Secret
from moneytor.domain.enums import AccountType, AssetClass, Currency, Institution
from moneytor.domain.models import Account, Holding
from moneytor.domain.money import Money
from moneytor.persistence.token_store import TokenStore

from ._parse import to_decimal, to_money
from .errors import AuthError, ConnectorError, FetchError, RateLimitError

_BASE_URL = "https://api.production.wealthsimple.com/v1/"
_TOKEN_PATH = "oauth/v2/token"
_TOKEN_INFO_PATH = "oauth/v2/token/info"
_GRAPHQL_URL = "https://my.wealthsimple.com/graphql"
_GRAPHQL_VERSION = "12"
_INSTITUTION_KEY = Institution.WEALTHSIMPLE.value
_OTP_HEADER = "x-wealthsimple-otp"
_WS_CLIENT_HEADER = "@wealthsimple/wealthsimple"
_CLIENT_SCOPE = "invest.read trade.read tax.read"
# Public client id used by the community-reverse-engineered Wealthsimple API.
_CLIENT_ID = "4da53ac2b03225bed1550eba8e4611e086c7b905a3855e6ed12ea08c246758fa"

OtpProvider = Callable[[], str]

# Wealthsimple's GraphQL ``type`` field -> our normalized account type.
_ACCOUNT_TYPES: dict[str, AccountType] = {
    "tfsa": AccountType.TFSA,
    "rrsp": AccountType.RRSP,
    "spousal_rrsp": AccountType.SPOUSAL_RRSP,
    "group_rrsp": AccountType.RRSP,
    "fhsa": AccountType.FHSA,
    "ca_cash": AccountType.CASH,
    "ca_cash_msb": AccountType.CASH,
    "non_registered": AccountType.CASH,
    "non_registered_crypto": AccountType.CASH,
    "managed": AccountType.MANAGED,
}
_SECURITY_TYPES: dict[str, AssetClass] = {
    "EQUITY": AssetClass.EQUITY,
    "ETF": AssetClass.ETF,
    "BOND": AssetClass.FIXED_INCOME,
    "CRYPTO": AssetClass.CRYPTO,
    "MUTUAL_FUND": AssetClass.OTHER,
    "OPTION": AssetClass.OTHER,
}
# Wealthsimple models cash as synthetic "securities" in the balances payload.
_CASH_SECURITIES: dict[str, Currency] = {
    "sec-c-cad": Currency.CAD,
    "sec-c-usd": Currency.USD,
}

_ACCOUNTS_QUERY = """
query Accounts($identityId: ID!, $cursor: String) {
  identity(id: $identityId) {
    accounts(filter: {}, first: 25, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      edges { node { id type currency status } }
    }
  }
}
"""
_POSITIONS_QUERY = """
query Positions($identityId: ID!, $currency: Currency!, $cursor: String) {
  identity(id: $identityId) {
    financials {
      current(currency: $currency) {
        positions(first: 100, after: $cursor) {
          pageInfo { hasNextPage endCursor }
          edges { node {
            quantity
            accounts { id }
            bookValue { amount currency }
            totalValue { amount currency }
            security { id securityType stock { symbol name primaryExchange } }
          } }
        }
      }
    }
  }
}
"""
_MARKET_DATA_QUERY = """
query SecurityMarketData($id: ID!) {
  security(id: $id) { id fundamentals { high52Week } }
}
"""
_BALANCES_QUERY = """
query Balances($ids: [String!]!, $type: BalanceType!) {
  accounts(ids: $ids) {
    id
    custodianAccounts {
      financials {
        ... on CustodianAccountFinancialsSo {
          balance(type: $type) { quantity securityId }
        }
      }
    }
  }
}
"""


@dataclass(frozen=True)
class _Session:
    access_token: str
    identity_id: str
    session_id: str


class WealthsimpleConnector:
    """A :class:`Connector` for Wealthsimple accounts (unofficial API)."""

    def __init__(
        self,
        person_id: str,
        email: str,
        password: Secret,
        otp_provider: OtpProvider | None = None,
        token_store: TokenStore | None = None,
        client: httpx.Client | None = None,
        base_url: str = _BASE_URL,
    ) -> None:
        self._person_id = person_id
        self._email = email
        self._password = password
        self._otp_provider = otp_provider
        self._token_store = token_store or TokenStore()
        self._client = client or httpx.Client(timeout=30.0)
        self._base_url = base_url.rstrip("/") + "/"
        self._session: _Session | None = None

    @property
    def institution(self) -> Institution:
        return Institution.WEALTHSIMPLE

    # -- auth --------------------------------------------------------------- #

    def authenticate(self) -> None:
        """Authenticate, preferring a stored refresh token over a fresh login."""
        stored = self._token_store.get(_INSTITUTION_KEY, self._person_id)
        if stored and self._try_refresh(stored):
            return
        self._password_login()

    def _try_refresh(self, refresh_token: str) -> bool:
        response = self._post_token(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": _CLIENT_ID,
            }
        )
        if response.status_code == httpx.codes.OK:
            self._store_session(response.json())
            return True
        return False

    def _password_login(self) -> None:
        body = {
            "grant_type": "password",
            "username": self._email,
            "password": self._password.reveal(),
            "scope": _CLIENT_SCOPE,
            "skip_provision": "true",
            "client_id": _CLIENT_ID,
            "otp_claim": "null",
        }
        response = self._post_token(body)

        if self._needs_otp(response):
            response = self._post_token(body, otp=self._request_otp())

        if response.status_code == httpx.codes.UNAUTHORIZED:
            raise AuthError("Wealthsimple rejected the credentials.")
        self._raise_for_status(response)
        self._store_session(response.json())

    def _needs_otp(self, response: httpx.Response) -> bool:
        return response.status_code == httpx.codes.UNAUTHORIZED and _OTP_HEADER in response.headers

    def _request_otp(self) -> str:
        if self._otp_provider is None:
            raise AuthError("Wealthsimple requires a 2FA code but no otp_provider was given.")
        code = self._otp_provider()
        if not code:
            raise AuthError("No 2FA code was provided.")
        return code

    def _store_session(self, data: object) -> None:
        if not isinstance(data, dict) or "access_token" not in data:
            raise AuthError("Wealthsimple auth response missing access_token.")
        refresh = data.get("refresh_token")
        if isinstance(refresh, str) and refresh:
            self._token_store.save(_INSTITUTION_KEY, self._person_id, refresh)
        access = str(data["access_token"])
        self._session = _Session(
            access_token=access,
            identity_id=self._fetch_identity(access),
            session_id=str(uuid.uuid4()),
        )

    def _fetch_identity(self, access_token: str) -> str:
        try:
            response = self._client.get(
                f"{self._base_url}{_TOKEN_INFO_PATH}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "x-wealthsimple-client": _WS_CLIENT_HEADER,
                },
            )
        except httpx.HTTPError as exc:
            raise FetchError(f"Wealthsimple token-info request failed: {exc}.") from exc
        self._raise_for_status(response)
        data = response.json()
        identity = data.get("identity_canonical_id") if isinstance(data, dict) else None
        if not identity:
            raise AuthError("Wealthsimple token-info missing identity_canonical_id.")
        return str(identity)

    def _post_token(self, body: dict[str, str], otp: str | None = None) -> httpx.Response:
        headers = {_OTP_HEADER: otp} if otp else None
        try:
            return self._client.post(f"{self._base_url}{_TOKEN_PATH}", json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise FetchError(f"Wealthsimple auth request failed: {exc}.") from exc

    # -- fetch -------------------------------------------------------------- #

    def fetch_accounts(self) -> tuple[Account, ...]:
        if self._session is None:
            raise ConnectorError("Call authenticate() before fetch_accounts().")
        identity = self._session.identity_id

        open_accounts = [n for n in self._account_nodes(identity) if n.get("status") == "open"]
        if not open_accounts:
            return ()
        open_ids = [str(n["id"]) for n in open_accounts]

        positions = self._positions_by_account(identity)
        balances = self._balances_by_account(open_ids)
        return tuple(self._build_account(n, positions, balances) for n in open_accounts)

    def _account_nodes(self, identity: str) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            data = self._graphql(
                "Accounts", _ACCOUNTS_QUERY, {"identityId": identity, "cursor": cursor}
            )
            connection = _nested(data, "identity", "accounts")
            nodes.extend(_edge_nodes(connection))
            cursor = _next_cursor(connection)
            if cursor is None:
                return nodes

    def _positions_by_account(self, identity: str) -> dict[str, list[Holding]]:
        nodes = self._position_nodes(identity)
        security_ids = sorted(
            {sid for node in nodes if (sid := _security_id(node))}
        )
        highs = self._high_52w_by_security(security_ids)

        grouped: dict[str, list[Holding]] = {}
        for node in nodes:
            holding = self._map_position(node, highs)
            for owner in node.get("accounts") or []:
                if isinstance(owner, dict) and owner.get("id"):
                    grouped.setdefault(str(owner["id"]), []).append(holding)
        return grouped

    def _position_nodes(self, identity: str) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            data = self._graphql(
                "Positions",
                _POSITIONS_QUERY,
                {"identityId": identity, "currency": Currency.CAD.value, "cursor": cursor},
            )
            connection = _nested(data, "identity", "financials", "current", "positions")
            nodes.extend(_edge_nodes(connection))
            cursor = _next_cursor(connection)
            if cursor is None:
                return nodes

    def _high_52w_by_security(self, security_ids: list[str]) -> dict[str, Decimal]:
        """52-week-high price per security id (one fundamentals call each).

        Best-effort: a security whose fundamentals fail/omit the value is simply
        absent from the result (its 52WHG shows as "—"). This is the slow part of
        a Wealthsimple fetch — one request per distinct holding.
        """
        highs: dict[str, Decimal] = {}
        for sid in security_ids:
            try:
                data = self._graphql("SecurityMarketData", _MARKET_DATA_QUERY, {"id": sid})
            except ConnectorError:
                continue
            security = data.get("security") if isinstance(data.get("security"), dict) else {}
            fundamentals = security.get("fundamentals") or {}
            value = fundamentals.get("high52Week")
            if value is not None:
                with suppress(FetchError):
                    highs[sid] = to_decimal(value, "fundamentals.high52Week")
        return highs

    def _balances_by_account(self, account_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        data = self._graphql("Balances", _BALANCES_QUERY, {"ids": account_ids, "type": "TRADING"})
        result: dict[str, list[dict[str, Any]]] = {}
        for account in data.get("accounts") or []:
            if not isinstance(account, dict):
                continue
            entries: list[dict[str, Any]] = []
            for custodian in account.get("custodianAccounts") or []:
                financials = custodian.get("financials") if isinstance(custodian, dict) else None
                balance = financials.get("balance") if isinstance(financials, dict) else None
                if isinstance(balance, list):
                    entries.extend(b for b in balance if isinstance(b, dict))
            result[str(account.get("id"))] = entries
        return result

    def _build_account(
        self,
        node: dict[str, Any],
        positions: dict[str, list[Holding]],
        balances: dict[str, list[dict[str, Any]]],
    ) -> Account:
        account_id = str(node["id"])
        cash, extra_cash = self._map_cash(balances.get(account_id, []))
        holdings = tuple(positions.get(account_id, ())) + extra_cash
        return Account(
            id=account_id,
            person_id=self._person_id,
            institution=Institution.WEALTHSIMPLE,
            account_type=_ACCOUNT_TYPES.get(str(node.get("type")), AccountType.CASH),
            cash=cash,
            holdings=holdings,
        )

    def _map_position(self, node: dict[str, Any], highs: dict[str, Decimal]) -> Holding:
        security = node.get("security") if isinstance(node.get("security"), dict) else {}
        stock = security.get("stock") if isinstance(security.get("stock"), dict) else {}
        symbol = stock.get("symbol") or security.get("id") or "UNKNOWN"
        market_value = _money_or_zero(node.get("totalValue"), "position.totalValue")
        high = highs.get(_security_id(node))
        return Holding(
            symbol=str(symbol),
            name=str(stock.get("name") or ""),
            exchange=str(stock.get("primaryExchange") or ""),
            asset_class=_SECURITY_TYPES.get(str(security.get("securityType")), AssetClass.OTHER),
            quantity=to_decimal(node.get("quantity", 0), "position.quantity"),
            book_value=_money_or_zero(node.get("bookValue"), "position.bookValue"),
            market_value=market_value,
            high_52w=Money(high, market_value.currency) if high is not None else None,
        )

    def _map_cash(self, entries: list[dict[str, Any]]) -> tuple[Money, tuple[Holding, ...]]:
        """Cash in its primary (CAD-preferred) currency; other currencies become
        synthetic CASH holdings so nothing is lost (mirrors the Questrade map)."""
        by_currency: dict[Currency, Decimal] = {}
        for entry in entries:
            currency = _CASH_SECURITIES.get(str(entry.get("securityId")))
            if currency is None:
                continue
            by_currency[currency] = to_decimal(entry.get("quantity", 0), "balance.quantity")

        if not by_currency:
            return Money.zero(Currency.CAD), ()
        primary = Currency.CAD if Currency.CAD in by_currency else next(iter(by_currency))
        cash = Money(by_currency[primary], primary)
        extra = tuple(
            Holding(
                symbol=f"CASH:{currency.value}",
                exchange="",
                asset_class=AssetClass.CASH,
                quantity=amount,
                book_value=Money(amount, currency),
                market_value=Money(amount, currency),
            )
            for currency, amount in by_currency.items()
            if currency is not primary and amount != 0
        )
        return cash, extra

    # -- http helpers ------------------------------------------------------- #

    def _graphql(self, operation: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        assert self._session is not None  # guarded by callers
        try:
            response = self._client.post(
                _GRAPHQL_URL,
                headers={
                    "Authorization": f"Bearer {self._session.access_token}",
                    "x-ws-profile": "trade",
                    "x-ws-api-version": _GRAPHQL_VERSION,
                    "x-ws-locale": "en-CA",
                    "x-platform-os": "web",
                    "x-ws-session-id": self._session.session_id,
                },
                json={"operationName": operation, "query": query, "variables": variables},
            )
        except httpx.HTTPError as exc:
            raise FetchError(f"Wealthsimple GraphQL {operation} failed: {exc}.") from exc
        self._raise_for_status(response)
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            errors = payload.get("errors") if isinstance(payload, dict) else payload
            raise FetchError(f"Wealthsimple GraphQL {operation} returned errors: {errors!r}.")
        return data

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        code = response.status_code
        if code == httpx.codes.UNAUTHORIZED:
            raise AuthError("Wealthsimple session is unauthorized (401).")
        if code == httpx.codes.TOO_MANY_REQUESTS:
            raise RateLimitError("Wealthsimple rate limit hit (429); retry later.")
        if code >= httpx.codes.BAD_REQUEST:
            raise FetchError(f"Wealthsimple returned HTTP {code}.")


# --------------------------------------------------------------------------- #
# GraphQL traversal helpers (defensive: never raise on a missing node)
# --------------------------------------------------------------------------- #


def _nested(data: dict[str, Any], *keys: str) -> dict[str, Any]:
    node: Any = data
    for key in keys:
        node = node.get(key) if isinstance(node, dict) else None
    return node if isinstance(node, dict) else {}


def _edge_nodes(connection: dict[str, Any]) -> list[dict[str, Any]]:
    edges = connection.get("edges") if isinstance(connection, dict) else None
    if not isinstance(edges, list):
        return []
    return [e["node"] for e in edges if isinstance(e, dict) and isinstance(e.get("node"), dict)]


def _next_cursor(connection: dict[str, Any]) -> str | None:
    page = connection.get("pageInfo") if isinstance(connection, dict) else None
    if isinstance(page, dict) and page.get("hasNextPage"):
        cursor = page.get("endCursor")
        return str(cursor) if cursor else None
    return None


def _money_or_zero(node: Any, where: str) -> Money:
    return to_money(node, where) if isinstance(node, dict) else Money.zero(Currency.CAD)


def _security_id(node: dict[str, Any]) -> str:
    security = node.get("security") if isinstance(node.get("security"), dict) else {}
    return str(security.get("id") or "")
