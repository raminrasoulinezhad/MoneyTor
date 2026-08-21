# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Properties that must hold for every portfolio, not just the fixtures.

Example-based tests check the cases we thought of. These generate randomized
portfolios (seeded, so a failure reproduces) and assert the invariants the
numbers on screen depend on: money reconciles, allocations sum to one, merging
does not care about input order, and no currency is ever silently mixed.
"""

from __future__ import annotations

import random
from decimal import Decimal

import pytest

from moneytor.aggregation import (
    allocation_by_symbol,
    build_snapshot,
    merge_holdings,
    totals_by_currency,
)
from moneytor.aggregation.normalize import currency_for_exchange
from moneytor.domain import AssetClass, Currency, Money, Person
from moneytor.domain.enums import AccountType, Institution
from moneytor.domain.errors import CurrencyMismatchError
from moneytor.domain.models import Account, Holding
from moneytor.fx import StaticFxProvider
from moneytor.ui.viewmodels import build_dashboard_view_model

USD_CAD = Decimal("1.376")
FX = StaticFxProvider(
    rates={
        (Currency.USD, Currency.CAD): USD_CAD,
        (Currency.CAD, Currency.USD): Decimal("1") / USD_CAD,
    }
)
_EXCHANGES = ("NYSE", "NASDAQ", "TSX", "TSX-V", "CSE", "", "SOME-VENUE")
_SYMBOLS = ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF")


def _portfolio(seed: int, *, people: int = 3, accounts: int = 3, holdings: int = 6):
    """A randomized but reproducible family portfolio."""
    rng = random.Random(seed)
    out = []
    for p in range(people):
        accts = []
        for a in range(accounts):
            hs = []
            for _ in range(rng.randint(0, holdings)):
                exchange = rng.choice(_EXCHANGES)
                currency = currency_for_exchange(exchange) or rng.choice(
                    (Currency.CAD, Currency.USD)
                )
                qty = Decimal(rng.randint(1, 500))
                price = Decimal(rng.randint(1, 40_000)) / Decimal(100)
                hs.append(
                    Holding(
                        symbol=rng.choice(_SYMBOLS),
                        name="N",
                        sector=rng.choice(("Energy", "Materials", "")),
                        exchange=exchange,
                        asset_class=rng.choice(tuple(AssetClass)),
                        quantity=qty,
                        book_value=Money(qty * price, currency),
                        market_value=Money(qty * price, currency),
                        high_52w=Money(price * Decimal("1.2"), currency),
                    )
                )
            accts.append(
                Account(
                    id=f"p{p}a{a}",
                    person_id=f"p{p}",
                    institution=rng.choice(tuple(Institution)),
                    account_type=rng.choice(tuple(AccountType)),
                    cash=Money(Decimal(rng.randint(0, 5000)), rng.choice(tuple(Currency))),
                    holdings=tuple(hs),
                )
            )
        out.append(Person(id=f"p{p}", name=f"P{p}", accounts=tuple(accts)))
    return tuple(out)


SEEDS = tuple(range(1, 26))


# --------------------------------------------------------------------------- #
# Money never mixes currencies
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("op", ["add", "sub", "lt", "gt"])
def test_cross_currency_operations_always_raise(op: str) -> None:
    cad, usd = Money.of("10", Currency.CAD), Money.of("10", Currency.USD)
    with pytest.raises(CurrencyMismatchError):
        {
            "add": lambda: cad + usd,
            "sub": lambda: cad - usd,
            "lt": lambda: cad < usd,
            "gt": lambda: cad > usd,
        }[op]()


@pytest.mark.parametrize("seed", SEEDS)
def test_every_money_value_on_the_dashboard_is_in_the_display_currency(seed: int) -> None:
    # A single stray native-currency value would make the totals lie.
    snapshot = build_snapshot(_portfolio(seed), Currency.CAD, FX)
    view = build_dashboard_view_model(snapshot, FX)

    for row in view.rows:
        assert row.value.currency is Currency.CAD
        if row.unit_price_display is not None:
            assert row.unit_price_display.currency is Currency.CAD
    for holding in snapshot.unified_holdings:
        assert holding.total_market_value.currency is Currency.CAD


# --------------------------------------------------------------------------- #
# Aggregation reconciles
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("seed", SEEDS)
def test_merged_quantities_equal_the_sum_of_their_sources(seed: int) -> None:
    holdings = [h for p in _portfolio(seed) for a in p.accounts for h in a.holdings]
    for unified in merge_holdings(holdings, Currency.CAD, FX):
        assert unified.total_quantity == sum((s.quantity for s in unified.sources), Decimal("0"))


@pytest.mark.parametrize("seed", SEEDS)
def test_merged_value_reconciles_with_the_converted_sources(seed: int) -> None:
    holdings = [h for p in _portfolio(seed) for a in p.accounts for h in a.holdings]
    for unified in merge_holdings(holdings, Currency.CAD, FX):
        expected = Money.zero(Currency.CAD)
        for source in unified.sources:
            rate = Decimal(1) if source.market_value.currency is Currency.CAD else USD_CAD
            expected += Money(source.market_value.amount * rate, Currency.CAD)
        # Per-source quantize in convert() allows at most a cent of drift each.
        drift = abs(unified.total_market_value.amount - expected.amount)
        assert drift <= Decimal("0.01") * len(unified.sources)


@pytest.mark.parametrize("seed", SEEDS)
def test_merge_is_order_independent(seed: int) -> None:
    holdings = [h for p in _portfolio(seed) for a in p.accounts for h in a.holdings]
    shuffled = list(holdings)
    random.Random(seed + 1000).shuffle(shuffled)

    first = merge_holdings(holdings, Currency.CAD, FX)
    second = merge_holdings(shuffled, Currency.CAD, FX)

    assert [u.symbol for u in first] == [u.symbol for u in second]
    assert [u.total_quantity for u in first] == [u.total_quantity for u in second]
    assert [u.total_market_value for u in first] == [u.total_market_value for u in second]


@pytest.mark.parametrize("seed", SEEDS)
def test_allocations_sum_to_one(seed: int) -> None:
    snapshot = build_snapshot(_portfolio(seed), Currency.CAD, FX)
    allocations = allocation_by_symbol(snapshot)
    if not allocations:
        pytest.skip("empty portfolio")
    total = sum(allocations.values(), Decimal("0"))
    if total == 0:
        return  # a portfolio with no value allocates nothing
    # 4dp rounding per symbol, so tolerance scales with the number of symbols.
    assert abs(total - Decimal("1")) <= Decimal("0.0001") * len(allocations)


@pytest.mark.parametrize("seed", SEEDS)
def test_allocations_are_never_negative_or_above_one(seed: int) -> None:
    snapshot = build_snapshot(_portfolio(seed), Currency.CAD, FX)
    for symbol, fraction in allocation_by_symbol(snapshot).items():
        assert Decimal("0") <= fraction <= Decimal("1"), symbol


@pytest.mark.parametrize("seed", SEEDS)
def test_totals_by_currency_keeps_each_currency_separate(seed: int) -> None:
    people = _portfolio(seed)
    totals = totals_by_currency(people)
    for currency, money in totals.items():
        assert money.currency is currency


# --------------------------------------------------------------------------- #
# Empty and degenerate portfolios must not raise
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "people",
    [
        (),
        (Person(id="a", name="A", accounts=()),),
        (
            Person(
                id="a",
                name="A",
                accounts=(
                    Account(
                        id="x",
                        person_id="a",
                        institution=Institution.QUESTRADE,
                        account_type=AccountType.TFSA,
                        cash=Money.zero(Currency.CAD),
                        holdings=(),
                    ),
                ),
            ),
        ),
    ],
    ids=["no-people", "no-accounts", "no-holdings"],
)
def test_degenerate_portfolios_render_without_error(people) -> None:
    snapshot = build_snapshot(people, Currency.CAD, FX)
    view = build_dashboard_view_model(snapshot, FX)
    assert view.rows == ()
    assert allocation_by_symbol(snapshot) == {}
    assert view.kpis  # the cards still render, showing zeros


def test_zero_quantity_holding_has_no_unit_price() -> None:
    # Dividing by a zero quantity must not raise or produce infinity.
    holding = Holding(
        symbol="ZZZ",
        name="Z",
        sector="",
        exchange="NYSE",
        asset_class=AssetClass.EQUITY,
        quantity=Decimal("0"),
        book_value=Money.zero(Currency.USD),
        market_value=Money.zero(Currency.USD),
    )
    snapshot = build_snapshot(
        (
            Person(
                id="a",
                name="A",
                accounts=(
                    Account(
                        id="x",
                        person_id="a",
                        institution=Institution.QUESTRADE,
                        account_type=AccountType.TFSA,
                        cash=Money.zero(Currency.CAD),
                        holdings=(holding,),
                    ),
                ),
            ),
        ),
        Currency.CAD,
        FX,
    )
    row = build_dashboard_view_model(snapshot, FX).rows[0]
    assert row.unit_price_native is None
    assert row.unit_price_text == "—"
