"""Tests for the pure dashboard view-models (Phase 6, no Qt)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from moneytor.aggregation import build_snapshot
from moneytor.connectors import load_accounts
from moneytor.domain import Currency, Person
from moneytor.fx import StaticFxProvider
from moneytor.ui.viewmodels import build_dashboard_view_model, view_model_for

CAD = Currency.CAD
USD = Currency.USD
FIXTURE = Path(__file__).parent.parent / "fixtures" / "mock_accounts.json"
PROVIDER = StaticFxProvider(rates={(USD, CAD): Decimal("1.35"), (CAD, USD): Decimal("0.74")})


def _people() -> tuple[Person, ...]:
    return (Person(id="ramin", name="Ramin", accounts=load_accounts(FIXTURE)),)


def test_view_model_has_three_kpis_and_total() -> None:
    snapshot = build_snapshot(_people(), CAD, PROVIDER)
    vm = build_dashboard_view_model(snapshot, PROVIDER)
    assert len(vm.kpis) == 3
    assert vm.kpis[0].title == "Total Portfolio Value"
    assert vm.kpis[0].value.startswith("$")  # number only
    assert "CAD" not in vm.kpis[0].value  # currency code lives in the subtitle
    assert vm.kpis[0].subtitle == "in CAD"
    assert vm.holding_count == 3
    assert vm.account_count == 2


def test_rows_sorted_by_value_desc() -> None:
    snapshot = build_snapshot(_people(), CAD, PROVIDER)
    vm = build_dashboard_view_model(snapshot, PROVIDER)
    values = [r.value.amount for r in vm.rows]
    assert values == sorted(values, reverse=True)
    assert vm.rows[0].symbol == "VFV"  # 3100 CAD is the largest


def test_allocation_percent_formatting() -> None:
    snapshot = build_snapshot(_people(), CAD, PROVIDER)
    vm = build_dashboard_view_model(snapshot, PROVIDER)
    assert vm.rows[0].allocation_pct.endswith("%")


def test_sidebar_lists_all_accounts() -> None:
    snapshot = build_snapshot(_people(), CAD, PROVIDER)
    vm = build_dashboard_view_model(snapshot, PROVIDER)
    assert len(vm.sidebar.people) == 1
    assert len(vm.sidebar.people[0].accounts) == 2


def test_filtering_by_account_reduces_rows_but_keeps_full_sidebar() -> None:
    people = _people()
    only_tfsa = view_model_for(people, CAD, PROVIDER, account_ids=frozenset({"qt-tfsa-ramin"}))
    assert only_tfsa.account_count == 1
    assert {r.symbol for r in only_tfsa.rows} == {"SHOP", "VFV"}
    # Sidebar still shows both accounts even when filtered.
    assert len(only_tfsa.sidebar.people[0].accounts) == 2


def test_empty_selection_via_none_shows_all() -> None:
    people = _people()
    vm = view_model_for(people, CAD, PROVIDER, account_ids=None)
    assert vm.holding_count == 3


def test_high_52w_pct_computed_in_native_currency() -> None:
    from dataclasses import replace

    from moneytor.domain import Account, AccountType, AssetClass, Holding, Institution, Money

    # AAPL: 2 shares worth $300 USD total -> $150/share; 52w high $200 USD.
    # 52WHG = (200 - 150) / 200 = 25% below the high.
    holding = Holding(
        symbol="AAPL",
        exchange="NASDAQ",
        asset_class=AssetClass.EQUITY,
        quantity=Decimal("2"),
        book_value=Money.of("250", USD),
        market_value=Money.of("300", USD),
        high_52w=Money.of("200", USD),
    )
    account = Account(
        id="a",
        person_id="p",
        institution=Institution.QUESTRADE,
        account_type=AccountType.MARGIN,
        cash=Money.zero(USD),
        holdings=(holding,),
    )
    people = (Person(id="p", name="P", accounts=(account,)),)
    vm = build_dashboard_view_model(build_snapshot(people, CAD, PROVIDER), PROVIDER)
    row = next(r for r in vm.rows if r.symbol == "AAPL")
    assert row.high_52w_pct == Decimal("0.25")
    assert row.high_52w_text == "25.0%"

    # A holding without a 52-week high reports None / "—".
    bare = replace(holding, symbol="ZZZ", high_52w=None)
    account2 = replace(account, holdings=(bare,))
    vm2 = build_dashboard_view_model(
        build_snapshot((Person(id="p", name="P", accounts=(account2,)),), CAD, PROVIDER), PROVIDER
    )
    assert vm2.rows[0].high_52w_pct is None
    assert vm2.rows[0].high_52w_text == "—"


def test_unit_price_in_native_currency_with_sub_cent_precision() -> None:
    from moneytor.domain import Account, AccountType, AssetClass, Holding, Institution, Money

    # 3 shares worth $100 USD total -> $33.3333.../share. The display currency is
    # CAD, but the unit price must stay in the security's native USD and keep
    # more than cent precision.
    holding = Holding(
        symbol="AAPL",
        exchange="NASDAQ",
        asset_class=AssetClass.EQUITY,
        quantity=Decimal("3"),
        book_value=Money.of("90", USD),
        market_value=Money.of("100", USD),
    )
    account = Account(
        id="a",
        person_id="p",
        institution=Institution.QUESTRADE,
        account_type=AccountType.MARGIN,
        cash=Money.zero(USD),
        holdings=(holding,),
    )
    people = (Person(id="p", name="P", accounts=(account,)),)
    vm = build_dashboard_view_model(build_snapshot(people, CAD, PROVIDER), PROVIDER)
    row = next(r for r in vm.rows if r.symbol == "AAPL")
    assert row.unit_price_native is not None
    assert row.unit_price_native.currency is USD  # native, not the CAD display currency
    # Unrounded Decimal kept on the model; formatted to 4 places for the table.
    assert row.unit_price_native.amount == Decimal("100") / Decimal("3")
    assert row.unit_price_text == "$33.3333 USD"
