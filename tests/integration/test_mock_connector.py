"""Integration tests for the connector framework + mock connector (Phase 4)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from moneytor.connectors import (
    AuthError,
    Connector,
    ConnectorError,
    FetchError,
    MockConnector,
    accounts_from_payload,
    load_accounts,
)
from moneytor.domain import AccountType, AssetClass, Currency, Institution, Money

FIXTURE = Path(__file__).parent.parent / "fixtures" / "mock_accounts.json"


# --------------------------------------------------------------------------- #
# Payload mapping
# --------------------------------------------------------------------------- #


def test_load_accounts_maps_fixture_to_domain_models() -> None:
    accounts = load_accounts(FIXTURE)
    assert len(accounts) == 3

    tfsa = accounts[0]
    assert tfsa.id == "qt-tfsa-ramin"
    assert tfsa.institution is Institution.QUESTRADE
    assert tfsa.account_type is AccountType.TFSA
    assert tfsa.cash == Money.of("1500.00", Currency.CAD)
    assert len(tfsa.holdings) == 2

    shop = tfsa.holdings[0]
    assert shop.symbol == "SHOP"
    assert shop.asset_class is AssetClass.EQUITY
    assert shop.quantity == Decimal("10")
    assert shop.market_value == Money.of("1200.50", Currency.CAD)


def test_account_rollup_from_fixture() -> None:
    accounts = load_accounts(FIXTURE)
    # CAD account: cash 1500 + 1200.50 + 3100 = 5800.50
    assert accounts[0].market_value() == Money.of("5800.50", Currency.CAD)


def test_malformed_payload_raises_fetch_error() -> None:
    with pytest.raises(FetchError, match="Malformed"):
        accounts_from_payload([{"id": "x"}])  # missing required fields


def test_bad_currency_raises_fetch_error() -> None:
    payload = [
        {
            "id": "a",
            "person_id": "p",
            "institution": "questrade",
            "account_type": "tfsa",
            "cash": {"amount": "1", "currency": "EUR"},
        }
    ]
    with pytest.raises(FetchError):
        accounts_from_payload(payload)


def test_missing_fixture_file_raises_fetch_error(tmp_path: Path) -> None:
    with pytest.raises(FetchError, match="Cannot read fixture"):
        load_accounts(tmp_path / "nope.json")


# --------------------------------------------------------------------------- #
# Connector protocol / lifecycle
# --------------------------------------------------------------------------- #


def test_mock_connector_satisfies_protocol() -> None:
    connector = MockConnector(institution=Institution.QUESTRADE)
    assert isinstance(connector, Connector)


def test_authenticate_then_fetch() -> None:
    connector = MockConnector.from_fixture(Institution.QUESTRADE, FIXTURE)
    connector.authenticate()
    accounts = connector.fetch_accounts()
    assert len(accounts) == 3


def test_fetch_before_authenticate_raises() -> None:
    connector = MockConnector.from_fixture(Institution.QUESTRADE, FIXTURE)
    with pytest.raises(ConnectorError, match="authenticate"):
        connector.fetch_accounts()


def test_auth_failure_raises_auth_error() -> None:
    connector = MockConnector(institution=Institution.WEALTHSIMPLE, fail_auth=True)
    with pytest.raises(AuthError):
        connector.authenticate()
