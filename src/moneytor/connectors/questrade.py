"""Questrade connector — official OAuth 2.0 API.

Auth flow (https://www.questrade.com/api/documentation):

1. A manually-issued *refresh token* (seeded via ``.env``) is exchanged at the
   login host for an ``access_token`` + ``api_server`` and a **new** refresh
   token (the old one is now invalid).
2. The rotated refresh token is persisted via :class:`TokenStore` so the next
   run can authenticate again.
3. Account/position/balance/symbol data is fetched from ``api_server`` and
   mapped into normalized domain models.

The ``httpx.Client`` is injectable so tests drive the connector with
``httpx.MockTransport`` and never touch the network.

``Any`` is used for decoded JSON nodes — these are external, loosely-typed API
payloads, validated as they are mapped into typed domain models below.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx

from moneytor.aggregation.normalize import normalize_sector
from moneytor.domain.enums import AccountType, AssetClass, Currency, Institution
from moneytor.domain.models import Account, Holding
from moneytor.domain.money import Money
from moneytor.persistence.token_store import TokenStore

from ._parse import to_currency as _currency
from ._parse import to_decimal as _decimal
from .errors import AuthError, ConnectorError, FetchError, RateLimitError

_LOGIN_HOST = "https://login.questrade.com"
_INSTITUTION_KEY = Institution.QUESTRADE.value

_ACCOUNT_TYPES: dict[str, AccountType] = {
    "Cash": AccountType.CASH,
    "Margin": AccountType.MARGIN,
    "TFSA": AccountType.TFSA,
    "RRSP": AccountType.RRSP,
    "SRRSP": AccountType.SPOUSAL_RRSP,
}
_SECURITY_TYPES: dict[str, AssetClass] = {
    "Stock": AssetClass.EQUITY,
    "Etf": AssetClass.ETF,
    "Bond": AssetClass.FIXED_INCOME,
    "MutualFund": AssetClass.OTHER,
}


def _price(value: Any, currency: Currency) -> Money | None:
    """Build a per-share price Money, or None when the broker omits/zeroes it."""
    if value in (None, 0, "0", ""):
        return None
    return Money(_decimal(value, "highPrice52"), currency)


@dataclass(frozen=True)
class _Session:
    access_token: str
    api_server: str


@dataclass(frozen=True)
class _SymbolInfo:
    currency: Currency
    asset_class: AssetClass
    name: str = ""
    sector: str = ""
    high_52w: Money | None = None


class QuestradeConnector:
    """A :class:`Connector` for Questrade accounts."""

    def __init__(
        self,
        person_id: str,
        seed_refresh_token: str,
        token_store: TokenStore | None = None,
        client: httpx.Client | None = None,
        login_host: str = _LOGIN_HOST,
    ) -> None:
        self._person_id = person_id
        self._seed = seed_refresh_token
        self._token_store = token_store or TokenStore()
        self._client = client or httpx.Client(timeout=30.0)
        self._login_host = login_host.rstrip("/")
        self._session: _Session | None = None

    @property
    def institution(self) -> Institution:
        return Institution.QUESTRADE

    # -- auth --------------------------------------------------------------- #

    def authenticate(self) -> None:
        token = self._token_store.get(_INSTITUTION_KEY, self._person_id) or self._seed
        if not token:
            raise AuthError(f"No Questrade refresh token for {self._person_id!r}.")
        try:
            response = self._client.get(
                f"{self._login_host}/oauth2/token",
                params={"grant_type": "refresh_token", "refresh_token": token},
            )
        except httpx.HTTPError as exc:
            raise FetchError(f"Questrade auth request failed: {exc}.") from exc
        self._raise_for_status(response)
        data = response.json()
        new_token = data.get("refresh_token")
        if not new_token or "access_token" not in data or "api_server" not in data:
            raise AuthError("Questrade auth response missing expected fields.")
        self._token_store.save(_INSTITUTION_KEY, self._person_id, new_token)
        self._session = _Session(
            access_token=data["access_token"],
            api_server=data["api_server"].rstrip("/") + "/",
        )

    # -- fetch -------------------------------------------------------------- #

    def fetch_accounts(self) -> tuple[Account, ...]:
        if self._session is None:
            raise ConnectorError("Call authenticate() before fetch_accounts().")
        accounts_node = self._get("v1/accounts").get("accounts", [])
        return tuple(self._map_account(node) for node in accounts_node)

    def _map_account(self, node: Any) -> Account:
        number = str(node["number"])
        positions = self._get(f"v1/accounts/{number}/positions").get("positions", [])
        balances = self._get(f"v1/accounts/{number}/balances")
        symbol_ids = [p["symbolId"] for p in positions if "symbolId" in p]
        symbols = self._symbol_info(symbol_ids)

        holdings = tuple(self._map_position(p, symbols) for p in positions)
        cash, extra_cash = self._map_cash(balances)
        return Account(
            id=number,
            person_id=self._person_id,
            institution=Institution.QUESTRADE,
            account_type=_ACCOUNT_TYPES.get(str(node.get("type")), AccountType.CASH),
            cash=cash,
            holdings=holdings + extra_cash,
        )

    def _map_position(self, node: Any, symbols: dict[int, _SymbolInfo]) -> Holding:
        info = symbols.get(node.get("symbolId"))
        if info is None:
            raise FetchError(f"Missing symbol info for position {node.get('symbol')!r}.")
        return Holding(
            symbol=str(node["symbol"]),
            name=info.name,
            sector=info.sector,
            high_52w=info.high_52w,
            exchange="",
            asset_class=info.asset_class,
            quantity=_decimal(node.get("openQuantity", 0), "position.openQuantity"),
            book_value=Money(_decimal(node.get("totalCost", 0), "totalCost"), info.currency),
            market_value=Money(
                _decimal(node.get("currentMarketValue", 0), "currentMarketValue"),
                info.currency,
            ),
        )

    def _map_cash(self, balances: Any) -> tuple[Money, tuple[Holding, ...]]:
        """Account cash in its primary (CAD-preferred) currency; other
        currencies become synthetic CASH holdings so nothing is lost."""
        by_currency: dict[Currency, Decimal] = {}
        for entry in balances.get("perCurrencyBalances", []):
            try:
                currency = Currency(entry["currency"])
            except (KeyError, ValueError):
                continue  # ignore unsupported currencies for cash
            by_currency[currency] = _decimal(entry.get("cash", 0), "balance.cash")

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

    def _symbol_info(self, symbol_ids: Iterable[int]) -> dict[int, _SymbolInfo]:
        ids = sorted({int(i) for i in symbol_ids})
        if not ids:
            return {}
        joined = ",".join(str(i) for i in ids)
        node = self._get("v1/symbols", params={"ids": joined})
        info: dict[int, _SymbolInfo] = {}
        for symbol in node.get("symbols", []):
            currency = _currency(symbol.get("currency"), "symbol.currency")
            info[int(symbol["symbolId"])] = _SymbolInfo(
                currency=currency,
                asset_class=_SECURITY_TYPES.get(str(symbol.get("securityType")), AssetClass.OTHER),
                name=str(symbol.get("description") or ""),
                sector=normalize_sector(str(symbol.get("industrySector") or "")),
                high_52w=_price(symbol.get("highPrice52"), currency),
            )
        return info

    # -- http helpers ------------------------------------------------------- #

    def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        assert self._session is not None  # guarded by callers
        try:
            response = self._client.get(
                f"{self._session.api_server}{path}",
                headers={"Authorization": f"Bearer {self._session.access_token}"},
                params=params,
            )
        except httpx.HTTPError as exc:
            raise FetchError(f"Questrade request to {path} failed: {exc}.") from exc
        self._raise_for_status(response)
        return response.json()

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        code = response.status_code
        if code == httpx.codes.UNAUTHORIZED:
            raise AuthError("Questrade rejected the credentials (401).")
        if code == httpx.codes.TOO_MANY_REQUESTS:
            raise RateLimitError("Questrade rate limit hit (429); retry later.")
        if code >= httpx.codes.BAD_REQUEST:
            raise FetchError(f"Questrade returned HTTP {code}.")
