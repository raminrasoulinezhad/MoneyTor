"""Tests for the aggregation engine (Phase 5)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from moneytor.aggregation import (
    AssetMap,
    account_value,
    allocation_by_symbol,
    build_snapshot,
    merge_holdings,
    person_value,
    totals_by_currency,
)
from moneytor.connectors import load_accounts
from moneytor.domain import (
    AccountType,
    AssetClass,
    Currency,
    Holding,
    Institution,
    Money,
    Person,
)
from moneytor.domain.models import Account
from moneytor.fx import StaticFxProvider

CAD = Currency.CAD
USD = Currency.USD
FIXTURE = Path(__file__).parent.parent / "fixtures" / "mock_accounts.json"

PROVIDER = StaticFxProvider(rates={(USD, CAD): Decimal("1.35"), (CAD, USD): Decimal("0.74")})


def _holding(symbol: str, exchange: str, currency: Currency, qty: str, mv: str) -> Holding:
    return Holding(
        symbol=symbol,
        exchange=exchange,
        asset_class=AssetClass.EQUITY,
        quantity=Decimal(qty),
        book_value=Money.of("0", currency),
        market_value=Money.of(mv, currency),
    )


# --------------------------------------------------------------------------- #
# Normalization
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("SHOP.TO", "SHOP"),
        ("shop.to", "SHOP"),
        ("BRK.B", "BRK.B"),  # share-class dot preserved
        ("AAPL", "AAPL"),
        (" vfv.to ", "VFV"),
    ],
)
def test_canonical_symbol(raw: str, expected: str) -> None:
    assert AssetMap().canonical(raw) == expected


def test_asset_map_override_wins() -> None:
    amap = AssetMap(overrides={"shop.to": "SHOP", "SHOPIFY": "SHOP"})
    assert amap.canonical("SHOPIFY") == "SHOP"
    assert amap.canonical("SHOP.TO") == "SHOP"


# --------------------------------------------------------------------------- #
# Merge
# --------------------------------------------------------------------------- #


def test_merge_unifies_same_asset_across_exchanges_and_currencies() -> None:
    holdings = [
        _holding("SHOP.TO", "TSX", CAD, "10", "1000.00"),
        _holding("SHOP", "NYSE", USD, "5", "400.00"),  # 400 USD -> 540 CAD
    ]
    unified = merge_holdings(holdings, CAD, PROVIDER)
    assert len(unified) == 1
    shop = unified[0]
    assert shop.symbol == "SHOP"
    assert shop.total_quantity == Decimal("15")
    assert shop.total_market_value == Money.of("1540.00", CAD)
    assert len(shop.sources) == 2


def test_merge_is_order_independent() -> None:
    a = _holding("SHOP.TO", "TSX", CAD, "10", "1000.00")
    b = _holding("SHOP", "NYSE", USD, "5", "400.00")
    forward = merge_holdings([a, b], CAD, PROVIDER)
    reverse = merge_holdings([b, a], CAD, PROVIDER)
    assert forward[0].total_market_value == reverse[0].total_market_value
    assert forward[0].total_quantity == reverse[0].total_quantity


def test_merge_results_sorted_by_symbol() -> None:
    holdings = [
        _holding("VFV", "TSX", CAD, "1", "10"),
        _holding("AAPL", "NASDAQ", USD, "1", "10"),
    ]
    unified = merge_holdings(holdings, CAD, PROVIDER)
    assert [u.symbol for u in unified] == ["AAPL", "VFV"]


# --------------------------------------------------------------------------- #
# Rollups & reconciliation
# --------------------------------------------------------------------------- #


def _fixture_people() -> tuple[Person, ...]:
    accounts = load_accounts(FIXTURE)
    return (Person(id="ramin", name="Ramin", accounts=accounts),)


def test_totals_by_currency_reconciles_to_sources() -> None:
    totals = totals_by_currency(_fixture_people())
    # CAD: cash 1500 + SHOP 1200.50 + VFV 3100 = 5800.50
    # USD: cash 300 + AAPL 950.75 = 1250.75
    assert totals[CAD] == Money.of("5800.50", CAD)
    assert totals[USD] == Money.of("1250.75", USD)


def test_account_value_cross_currency() -> None:
    accounts = load_accounts(FIXTURE)
    usd_account = accounts[1]  # margin, USD
    # (300 + 950.75) USD * 1.35 = 1688.5125 -> 1688.51
    assert account_value(usd_account, CAD, PROVIDER) == Money.of("1688.51", CAD)


def test_person_value_sums_accounts() -> None:
    person = _fixture_people()[0]
    # CAD account 5800.50 + USD account 1688.51 (converted) = 7489.01
    assert person_value(person, CAD, PROVIDER) == Money.of("7489.01", CAD)


def test_empty_account_value_is_cash_only() -> None:
    account = Account(
        id="x",
        person_id="p",
        institution=Institution.QUESTRADE,
        account_type=AccountType.CASH,
        cash=Money.of("42", CAD),
    )
    assert account_value(account, CAD, PROVIDER) == Money.of("42.00", CAD)


# --------------------------------------------------------------------------- #
# Snapshot & allocation
# --------------------------------------------------------------------------- #


def test_build_snapshot_end_to_end() -> None:
    snapshot = build_snapshot(_fixture_people(), CAD, PROVIDER, as_of="2026-06-06")
    assert snapshot.display_currency is CAD
    assert snapshot.as_of == "2026-06-06"
    symbols = {u.symbol for u in snapshot.unified_holdings}
    assert symbols == {"SHOP", "VFV", "AAPL"}


def test_allocation_sums_to_one() -> None:
    snapshot = build_snapshot(_fixture_people(), CAD, PROVIDER)
    allocations = allocation_by_symbol(snapshot)
    assert sum(allocations.values()) == pytest.approx(Decimal("1"), abs=Decimal("0.001"))


def test_allocation_empty_portfolio() -> None:
    snapshot = build_snapshot((), CAD, PROVIDER)
    assert allocation_by_symbol(snapshot) == {}
