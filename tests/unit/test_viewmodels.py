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
    assert "CAD" in vm.kpis[0].value
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
