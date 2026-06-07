"""Questrade connector tests driven by httpx.MockTransport (no network)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from moneytor.connectors import (
    AuthError,
    Connector,
    ConnectorError,
    QuestradeConnector,
    RateLimitError,
)
from moneytor.domain import AccountType, AssetClass, Currency, Money
from moneytor.persistence import TokenStore

API = "https://api01.iq.questrade.com/"

_ACCOUNTS = {"accounts": [{"type": "TFSA", "number": "26598145", "status": "Active"}]}
_POSITIONS = {
    "positions": [
        {
            "symbol": "AAPL",
            "symbolId": 8049,
            "openQuantity": 10,
            "currentMarketValue": 1950.50,
            "totalCost": 1500.00,
        }
    ]
}
_BALANCES = {
    "perCurrencyBalances": [
        {"currency": "CAD", "cash": 1000.00, "totalEquity": 1000.00},
        {"currency": "USD", "cash": 250.00, "totalEquity": 2200.50},
    ]
}
_SYMBOLS = {
    "symbols": [{"symbol": "AAPL", "symbolId": 8049, "currency": "USD", "securityType": "Stock"}]
}

_TOKEN_OK = {
    "access_token": "access-xyz",
    "token_type": "Bearer",
    "expires_in": 1800,
    "refresh_token": "rotated-token-2",
    "api_server": API,
}


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/oauth2/token":
        return httpx.Response(200, json=_TOKEN_OK)
    if path == "/v1/accounts":
        return httpx.Response(200, json=_ACCOUNTS)
    if path.endswith("/positions"):
        return httpx.Response(200, json=_POSITIONS)
    if path.endswith("/balances"):
        return httpx.Response(200, json=_BALANCES)
    if path == "/v1/symbols":
        return httpx.Response(200, json=_SYMBOLS)
    return httpx.Response(404, json={"message": "not found"})


def _client(handler=_handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _connector(tmp_path: Path, handler=_handler) -> QuestradeConnector:
    store = TokenStore(tmp_path / "tokens.json")
    return QuestradeConnector(
        person_id="ramin",
        seed_refresh_token="seed-token-1",
        token_store=store,
        client=_client(handler),
    )


# --------------------------------------------------------------------------- #
# Auth & token rotation
# --------------------------------------------------------------------------- #


def test_connector_satisfies_protocol(tmp_path: Path) -> None:
    assert isinstance(_connector(tmp_path), Connector)


def test_authenticate_persists_rotated_token(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "tokens.json")
    connector = QuestradeConnector(
        person_id="ramin",
        seed_refresh_token="seed-token-1",
        token_store=store,
        client=_client(),
    )
    connector.authenticate()
    assert store.get("questrade", "ramin") == "rotated-token-2"


def test_cached_token_preferred_over_seed(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "tokens.json")
    store.save("questrade", "ramin", "cached-token")
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/token":
            captured.append(dict(request.url.params)["refresh_token"])
        return _handler(request)

    connector = QuestradeConnector(
        person_id="ramin",
        seed_refresh_token="seed-token-1",
        token_store=store,
        client=_client(handler),
    )
    connector.authenticate()
    assert captured == ["cached-token"]


def test_auth_401_raises_auth_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "bad token"})

    with pytest.raises(AuthError):
        _connector(tmp_path, handler).authenticate()


def test_missing_seed_raises_auth_error(tmp_path: Path) -> None:
    connector = QuestradeConnector(
        person_id="ramin",
        seed_refresh_token="",
        token_store=TokenStore(tmp_path / "tokens.json"),
        client=_client(),
    )
    with pytest.raises(AuthError, match="No Questrade refresh token"):
        connector.authenticate()


# --------------------------------------------------------------------------- #
# Fetch & mapping
# --------------------------------------------------------------------------- #


def test_fetch_before_authenticate_raises(tmp_path: Path) -> None:
    with pytest.raises(ConnectorError, match="authenticate"):
        _connector(tmp_path).fetch_accounts()


def test_fetch_accounts_maps_payload(tmp_path: Path) -> None:
    connector = _connector(tmp_path)
    connector.authenticate()
    accounts = connector.fetch_accounts()

    assert len(accounts) == 1
    account = accounts[0]
    assert account.id == "26598145"
    assert account.account_type is AccountType.TFSA
    # Primary cash is CAD; USD cash becomes a synthetic CASH holding.
    assert account.cash == Money.of("1000.00", Currency.CAD)

    aapl = next(h for h in account.holdings if h.symbol == "AAPL")
    assert aapl.asset_class is AssetClass.EQUITY
    assert aapl.quantity == Decimal("10")
    assert aapl.market_value == Money.of("1950.50", Currency.USD)

    usd_cash = next(h for h in account.holdings if h.symbol == "CASH:USD")
    assert usd_cash.asset_class is AssetClass.CASH
    assert usd_cash.market_value == Money.of("250.00", Currency.USD)


def test_rate_limit_raises(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/accounts":
            return httpx.Response(429, json={"message": "slow down"})
        return _handler(request)

    connector = _connector(tmp_path, handler)
    connector.authenticate()
    with pytest.raises(RateLimitError):
        connector.fetch_accounts()
