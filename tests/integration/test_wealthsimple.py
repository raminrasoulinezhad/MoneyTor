"""Wealthsimple connector tests via httpx.MockTransport (no network).

Validates the auth state machine (refresh, password grant, OTP-challenge retry,
identity lookup) and the GraphQL account/position/balance mapping against the
validated-but-unofficial API shapes.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from moneytor.config.secret import Secret
from moneytor.connectors import (
    AuthError,
    Connector,
    ConnectorError,
    WealthsimpleConnector,
)
from moneytor.domain import AccountType, AssetClass, Currency, Money
from moneytor.persistence import TokenStore

_TOKEN_OK = {"access_token": "acc", "refresh_token": "refresh-2", "expires_in": 3600}
_IDENTITY = {"identity_canonical_id": "identity-1"}

_ACCOUNTS = {
    "data": {
        "identity": {
            "accounts": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "edges": [
                    {"node": {"id": "tfsa-1", "type": "tfsa", "currency": "CAD", "status": "open"}},
                    {
                        "node": {
                            "id": "old-1",
                            "type": "rrsp",
                            "currency": "CAD",
                            "status": "closed",
                        }
                    },
                ],
            }
        }
    }
}
_POSITIONS = {
    "data": {
        "identity": {
            "financials": {
                "current": {
                    "positions": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "edges": [
                            {
                                "node": {
                                    "quantity": "20",
                                    "accounts": [{"id": "tfsa-1"}],
                                    "bookValue": {"amount": "600.00", "currency": "CAD"},
                                    "totalValue": {"amount": "720.00", "currency": "CAD"},
                                    "security": {
                                        "securityType": "ETF",
                                        "stock": {
                                            "symbol": "VEQT",
                                            "name": "Vanguard All-Equity ETF",
                                            "primaryExchange": "TSX",
                                        },
                                    },
                                }
                            }
                        ],
                    }
                }
            }
        }
    }
}
_BALANCES = {
    "data": {
        "accounts": [
            {
                "id": "tfsa-1",
                "custodianAccounts": [
                    {
                        "financials": {
                            "balance": [
                                {"securityId": "sec-c-cad", "quantity": "500.00"},
                                {"securityId": "sec-s-veqt", "quantity": "20"},
                            ]
                        }
                    }
                ],
            }
        ]
    }
}

_GRAPHQL_RESPONSES = {"Accounts": _ACCOUNTS, "Positions": _POSITIONS, "Balances": _BALANCES}


def _data_handler(request: httpx.Request) -> httpx.Response | None:
    """Serve token-info + GraphQL data routes (shared by the happy-path tests)."""
    path = request.url.path
    if path.endswith("/oauth/v2/token/info"):
        return httpx.Response(200, json=_IDENTITY)
    if path.endswith("/graphql"):
        operation = json.loads(request.content)["operationName"]
        return httpx.Response(200, json=_GRAPHQL_RESPONSES[operation])
    return None


def _connector(handler, tmp_path: Path, otp_provider=None) -> WealthsimpleConnector:
    return WealthsimpleConnector(
        person_id="ramin",
        email="r@example.com",
        password=Secret("pw"),
        otp_provider=otp_provider,
        token_store=TokenStore(tmp_path / "tokens.json"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #


def test_connector_satisfies_protocol(tmp_path: Path) -> None:
    assert isinstance(_connector(lambda r: httpx.Response(200, json={}), tmp_path), Connector)


def test_password_login_without_2fa(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth/v2/token"):
            return httpx.Response(200, json=_TOKEN_OK)
        return _data_handler(request) or httpx.Response(404)

    connector = _connector(handler, tmp_path)
    connector.authenticate()
    accounts = connector.fetch_accounts()
    assert accounts[0].account_type is AccountType.TFSA


def test_otp_challenge_then_retry_with_code(tmp_path: Path) -> None:
    calls = {"token": 0}
    seen_codes: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth/v2/token"):
            calls["token"] += 1
            seen_codes.append(request.headers.get("x-wealthsimple-otp"))
            if calls["token"] == 1:
                return httpx.Response(401, headers={"x-wealthsimple-otp": "required; method=app"})
            return httpx.Response(200, json=_TOKEN_OK)
        return _data_handler(request) or httpx.Response(404)

    connector = _connector(handler, tmp_path, otp_provider=lambda: "123456")
    connector.authenticate()
    assert calls["token"] == 2
    assert seen_codes == [None, "123456"]
    assert connector.fetch_accounts()[0].id == "tfsa-1"


def test_otp_required_but_no_provider_raises(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, headers={"x-wealthsimple-otp": "required"})

    with pytest.raises(AuthError, match="no otp_provider"):
        _connector(handler, tmp_path).authenticate()


def test_stored_refresh_token_skips_password_login(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "tokens.json")
    store.save("wealthsimple", "ramin", "stored-refresh")
    grants: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth/v2/token"):
            grants.append(json.loads(request.content)["grant_type"])
            return httpx.Response(200, json=_TOKEN_OK)
        return _data_handler(request) or httpx.Response(404)

    connector = WealthsimpleConnector(
        person_id="ramin",
        email="r@example.com",
        password=Secret("pw"),
        token_store=store,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    connector.authenticate()
    assert grants == ["refresh_token"]  # never fell back to password


def test_bad_credentials_raise_auth_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401)  # 401 with no OTP header => bad creds

    with pytest.raises(AuthError):
        _connector(handler, tmp_path).authenticate()


def test_missing_identity_raises_auth_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth/v2/token"):
            return httpx.Response(200, json=_TOKEN_OK)
        if request.url.path.endswith("/oauth/v2/token/info"):
            return httpx.Response(200, json={})  # no identity_canonical_id
        return httpx.Response(404)

    with pytest.raises(AuthError, match="identity"):
        _connector(handler, tmp_path).authenticate()


# --------------------------------------------------------------------------- #
# Fetch & mapping
# --------------------------------------------------------------------------- #


def _authenticated(tmp_path: Path) -> WealthsimpleConnector:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth/v2/token"):
            return httpx.Response(200, json=_TOKEN_OK)
        return _data_handler(request) or httpx.Response(404)

    connector = _connector(handler, tmp_path)
    connector.authenticate()
    return connector


def test_fetch_before_authenticate_raises(tmp_path: Path) -> None:
    connector = _connector(lambda r: httpx.Response(200, json={}), tmp_path)
    with pytest.raises(ConnectorError, match="authenticate"):
        connector.fetch_accounts()


def test_closed_accounts_are_filtered_out(tmp_path: Path) -> None:
    accounts = _authenticated(tmp_path).fetch_accounts()
    assert [a.id for a in accounts] == ["tfsa-1"]  # 'old-1' is closed


def test_maps_positions_and_cash(tmp_path: Path) -> None:
    account = _authenticated(tmp_path).fetch_accounts()[0]
    assert account.cash == Money.of("500.00", Currency.CAD)
    veqt = account.holdings[0]
    assert veqt.symbol == "VEQT"
    assert veqt.name == "Vanguard All-Equity ETF"
    assert veqt.exchange == "TSX"
    assert veqt.asset_class is AssetClass.ETF
    assert veqt.quantity == Decimal("20")
    assert veqt.book_value == Money.of("600.00", Currency.CAD)
    assert veqt.market_value == Money.of("720.00", Currency.CAD)


def test_graphql_errors_raise_fetch_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth/v2/token"):
            return httpx.Response(200, json=_TOKEN_OK)
        if request.url.path.endswith("/oauth/v2/token/info"):
            return httpx.Response(200, json=_IDENTITY)
        if request.url.path.endswith("/graphql"):
            return httpx.Response(200, json={"errors": [{"message": "boom"}]})
        return httpx.Response(404)

    connector = _connector(handler, tmp_path)
    connector.authenticate()
    with pytest.raises(ConnectorError, match="errors"):
        connector.fetch_accounts()
