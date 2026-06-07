"""Wealthsimple connector — UNOFFICIAL API.

Wealthsimple publishes no official/documented API. This connector targets the
well-known community OAuth flow:

1. Password grant (email + password). If 2FA is enabled, the first request is
   rejected with an OTP challenge (an ``x-wealthsimple-otp`` response header);
   the request is then retried with the user-supplied code in the
   ``x-wealthsimple-otp`` request header.
2. The returned refresh token is persisted via :class:`TokenStore` so later
   runs can refresh silently (no 2FA prompt) until it expires.
3. Accounts and positions are fetched and mapped into normalized domain models.

The OTP code is obtained from an injected ``otp_provider`` callable (a GUI
dialog in the app, ``input()`` in a CLI, or a fixed value in tests).

⚠️ The endpoint paths and payload shapes below are documented *assumptions*
based on the community-reverse-engineered API. They must be validated against
the live service with real credentials; they are centralized here so tuning is
a one-file change. All parsing is defensive and raises ``FetchError`` on
mismatch rather than crashing.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from moneytor.config.secret import Secret
from moneytor.domain.enums import AccountType, AssetClass, Institution
from moneytor.domain.models import Account, Holding
from moneytor.persistence.token_store import TokenStore

from ._parse import to_decimal, to_money
from .errors import AuthError, ConnectorError, FetchError, RateLimitError

_BASE_URL = "https://api.production.wealthsimple.com/v1/"
_INSTITUTION_KEY = Institution.WEALTHSIMPLE.value
_OTP_HEADER = "x-wealthsimple-otp"
_CLIENT_SCOPE = "invest.read trade.read"

OtpProvider = Callable[[], str]

_ACCOUNT_TYPES: dict[str, AccountType] = {
    "ca_tfsa": AccountType.TFSA,
    "ca_rrsp": AccountType.RRSP,
    "ca_spousal_rrsp": AccountType.SPOUSAL_RRSP,
    "ca_non_registered": AccountType.CASH,
    "ca_non_registered_margin": AccountType.MARGIN,
    "managed": AccountType.MANAGED,
}
_SECURITY_TYPES: dict[str, AssetClass] = {
    "equity": AssetClass.EQUITY,
    "etf": AssetClass.ETF,
    "bond": AssetClass.FIXED_INCOME,
    "crypto": AssetClass.CRYPTO,
}


@dataclass(frozen=True)
class _Session:
    access_token: str


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
        response = self._post_token({"grant_type": "refresh_token", "refresh_token": refresh_token})
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
        self._session = _Session(access_token=str(data["access_token"]))

    def _post_token(self, body: dict[str, str], otp: str | None = None) -> httpx.Response:
        headers = {_OTP_HEADER: otp} if otp else None
        try:
            return self._client.post(f"{self._base_url}oauth/token", json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise FetchError(f"Wealthsimple auth request failed: {exc}.") from exc

    # -- fetch -------------------------------------------------------------- #

    def fetch_accounts(self) -> tuple[Account, ...]:
        if self._session is None:
            raise ConnectorError("Call authenticate() before fetch_accounts().")
        accounts_node = self._get("account/list").get("results", [])
        return tuple(self._map_account(node) for node in accounts_node)

    def _map_account(self, node: Any) -> Account:
        if not isinstance(node, dict):
            raise FetchError(f"Malformed account node: {node!r}.")
        account_id = str(node["id"])
        positions = self._get("account/positions", params={"account_id": account_id}).get(
            "results", []
        )
        return Account(
            id=account_id,
            person_id=self._person_id,
            institution=Institution.WEALTHSIMPLE,
            account_type=_ACCOUNT_TYPES.get(str(node.get("type")), AccountType.CASH),
            cash=to_money(node.get("cash", {}), "account.cash"),
            holdings=tuple(self._map_position(p) for p in positions),
        )

    def _map_position(self, node: Any) -> Holding:
        if not isinstance(node, dict):
            raise FetchError(f"Malformed position node: {node!r}.")
        return Holding(
            symbol=str(node["symbol"]),
            exchange=str(node.get("exchange", "")),
            asset_class=_SECURITY_TYPES.get(str(node.get("security_type")), AssetClass.OTHER),
            quantity=to_decimal(node.get("quantity", 0), "position.quantity"),
            book_value=to_money(node.get("book_value", {}), "position.book_value"),
            market_value=to_money(node.get("market_value", {}), "position.market_value"),
        )

    # -- http helpers ------------------------------------------------------- #

    def _get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        assert self._session is not None  # guarded by callers
        try:
            response = self._client.get(
                f"{self._base_url}{path}",
                headers={"Authorization": f"Bearer {self._session.access_token}"},
                params=params,
            )
        except httpx.HTTPError as exc:
            raise FetchError(f"Wealthsimple request to {path} failed: {exc}.") from exc
        self._raise_for_status(response)
        data = response.json()
        if not isinstance(data, dict):
            raise FetchError(f"Wealthsimple {path} returned a non-object response.")
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
