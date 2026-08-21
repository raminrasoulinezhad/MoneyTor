# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Pure view-models adapting domain data to the dashboard.

This module has **no Qt imports** so it is unit-testable without a display and
keeps the GUI decoupled from the domain (CLAUDE.md modular-design rule). It
reuses the aggregation engine for all math.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from moneytor.aggregation import (
    allocation_by_symbol,
    annual_dividend_income,
    annual_gic_interest,
    build_snapshot,
    person_value,
)
from moneytor.aggregation.normalize import currency_for_exchange
from moneytor.domain.enums import Currency
from moneytor.domain.models import Person, PortfolioSnapshot, UnifiedHolding
from moneytor.domain.money import Money
from moneytor.fx.convert import convert
from moneytor.fx.provider import FxProvider


def _native_currency(holding: UnifiedHolding) -> Currency:
    """The currency a quote for this security is denominated in.

    Taken from the listing venue, because a broker's reported currency may be
    one it converted to on our behalf rather than the security's own
    (Wealthsimple returns every position in CAD). Falls back to the first
    source's reported currency when no source names a venue we recognise.
    """
    for source in holding.sources:
        currency = currency_for_exchange(source.exchange)
        if currency is not None:
            return currency
    return holding.sources[0].market_value.currency


def _native_unit_price(holding: UnifiedHolding, provider: FxProvider | None = None) -> Money | None:
    """Current price per unit, in the security's native currency.

    Every source for one security carries the same underlying price, just
    possibly expressed in different currencies — the same US stock arrives from
    Questrade in USD and from Wealthsimple pre-converted to CAD. So this uses
    only the sources already reported in the native currency and ignores the
    rest: their amounts need no FX, and mixing currencies here would average a
    USD price with a CAD one into a number that is neither.

    The division is left unrounded so the table can show sub-cent precision.
    Returns None with no sources, zero quantity, or no source in the native
    currency (rather than inventing a rate).
    """
    if not holding.sources or holding.total_quantity == 0:
        return None
    native = _native_currency(holding)
    native_sources = [s for s in holding.sources if s.market_value.currency is native]
    quantity = sum((s.quantity for s in native_sources), Decimal("0"))
    if native_sources and quantity != 0:
        value = sum((s.market_value.amount for s in native_sources), Decimal("0"))
        return Money(value / quantity, native)
    # No source reports in the native currency — a US listing held only through
    # Wealthsimple, say, which converts everything to CAD. Convert instead of
    # dropping the price, which is still better than showing nothing.
    if provider is None:
        return None
    converted = Money.zero(native)
    for source in holding.sources:
        converted += convert(source.market_value, native, provider)
    return Money(converted.amount / holding.total_quantity, native)


def _high_52w_pct(holding: UnifiedHolding, provider: FxProvider | None = None) -> Decimal | None:
    """How far below the 52-week high the current price sits, as a fraction.

    ``(52-week high - current price) / 52-week high`` — 0 means at the high,
    larger means further below it. Computed in the security's native currency
    (both the high and the unit price are native), so it is FX-independent.
    Returns None when the high or the native price is unavailable.
    """
    if holding.high_52w is None or holding.high_52w.amount == 0:
        return None
    price = _native_unit_price(holding, provider)
    if price is None:
        return None
    high = holding.high_52w
    if high.currency is not price.currency:
        # A cache written before the 52-week high was tagged from the listing
        # venue can disagree with the price; convert rather than compare across
        # currencies, which would report a meaningless gap.
        if provider is None:
            return None
        high = convert(high, price.currency, provider)
        if high.amount == 0:
            return None
    return (high.amount - price.amount) / high.amount


@dataclass(frozen=True)
class HoldingRow:
    """One row of the holdings table."""

    symbol: str
    asset_class: str
    quantity: Decimal
    value: Money
    allocation: Decimal  # fraction of total (0..1)
    name: str = ""
    sector: str = ""
    high_52w_pct: Decimal | None = None  # current price / 52-week high (0..1+)
    unit_price_native: Money | None = None  # price per unit in original currency

    @property
    def allocation_pct(self) -> str:
        return f"{self.allocation * 100:.1f}%"

    @property
    def high_52w_text(self) -> str:
        if self.high_52w_pct is None:
            return "—"
        return f"{self.high_52w_pct * 100:.1f}%"

    @property
    def unit_price_text(self) -> str:
        """Unit price with two-decimal precision and its original currency code."""
        if self.unit_price_native is None:
            return "—"
        return self.unit_price_native.format(places=2)


@dataclass(frozen=True)
class KpiModel:
    """A single KPI card's content."""

    title: str
    value: str
    subtitle: str = ""
    tone: str = "neutral"  # neutral | positive | negative
    # True for cards carrying an absolute monetary figure (masked in private mode).
    sensitive: bool = False


@dataclass(frozen=True)
class SidebarAccount:
    id: str
    label: str


@dataclass(frozen=True)
class SidebarPerson:
    id: str
    name: str
    accounts: tuple[SidebarAccount, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SidebarModel:
    people: tuple[SidebarPerson, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DashboardViewModel:
    """Everything the dashboard needs to render one (filtered) view."""

    total_value: Money
    holding_count: int
    account_count: int
    kpis: tuple[KpiModel, ...]
    rows: tuple[HoldingRow, ...]
    sidebar: SidebarModel


def filter_people(
    people: tuple[Person, ...], account_ids: frozenset[str] | None
) -> tuple[Person, ...]:
    """Keep only the selected accounts; ``None`` means "all".

    People left with no selected accounts are dropped from the result.
    """
    if account_ids is None:
        return people
    filtered: list[Person] = []
    for person in people:
        kept = tuple(a for a in person.accounts if a.id in account_ids)
        if kept:
            filtered.append(Person(id=person.id, name=person.name, accounts=kept))
    return tuple(filtered)


def _sidebar_from(people: tuple[Person, ...]) -> SidebarModel:
    return SidebarModel(
        people=tuple(
            SidebarPerson(
                id=p.id,
                name=p.name,
                accounts=tuple(
                    SidebarAccount(
                        id=a.id,
                        label=f"{a.account_type.value.upper()} · {a.institution.value}",
                    )
                    for a in p.accounts
                ),
            )
            for p in people
        )
    )


def build_dashboard_view_model(
    snapshot: PortfolioSnapshot, provider: FxProvider
) -> DashboardViewModel:
    """Adapt a :class:`PortfolioSnapshot` into a :class:`DashboardViewModel`."""
    currency = snapshot.display_currency
    total = Money.zero(currency)
    for person in snapshot.people:
        total += person_value(person, currency, provider)

    allocations = allocation_by_symbol(snapshot)
    rows = tuple(
        sorted(
            (
                HoldingRow(
                    symbol=u.symbol,
                    name=u.name,
                    sector=u.sector,
                    asset_class=u.asset_class.value,
                    quantity=u.total_quantity,
                    value=u.total_market_value,
                    allocation=allocations.get(u.symbol, Decimal("0")),
                    high_52w_pct=_high_52w_pct(u, provider),
                    unit_price_native=_native_unit_price(u, provider),
                )
                for u in snapshot.unified_holdings
            ),
            key=lambda r: r.value.amount,
            reverse=True,
        )
    )

    account_count = sum(len(p.accounts) for p in snapshot.people)
    top = rows[0] if rows else None
    dividends = annual_dividend_income(snapshot)
    gic_interest = annual_gic_interest(snapshot)
    total_income = dividends + gic_interest
    portfolio_yield = dividends.amount / total.amount * 100 if total.amount else Decimal("0")
    kpis = (
        # Currency shown once, in the subtitle — keeps the big number short so
        # it doesn't truncate in the card.
        KpiModel(
            "Total Portfolio Value",
            total.format(with_currency=False),
            f"in {currency.value}",
            sensitive=True,
        ),
        # Rough estimated yearly dividend income; subtitle shows the implied
        # portfolio-wide yield. Big number stays currency-free like the total.
        KpiModel(
            "Est. Annual Dividends",
            dividends.format(with_currency=False),
            f"≈ {portfolio_yield:.1f}% yield · in {currency.value}",
            sensitive=True,
        ),
        # Rough estimated yearly GIC interest (rate parsed from each GIC's name).
        KpiModel(
            "Est. GIC Interest",
            gic_interest.format(with_currency=False),
            f"in {currency.value}",
            sensitive=True,
        ),
        # Combined passive income: dividends + GIC interest.
        KpiModel(
            "Est. Annual Income",
            total_income.format(with_currency=False),
            "dividends + GIC interest",
            sensitive=True,
        ),
        KpiModel("Holdings", str(len(rows)), f"across {account_count} accounts"),
        KpiModel(
            "Top Position",
            top.symbol if top else "—",
            f"{top.allocation_pct} of portfolio" if top else "no holdings",
        ),
    )

    return DashboardViewModel(
        total_value=total.quantize(),
        holding_count=len(rows),
        account_count=account_count,
        kpis=kpis,
        rows=rows,
        sidebar=_sidebar_from(snapshot.people),
    )


def view_model_for(
    people: tuple[Person, ...],
    display_currency: Currency,
    provider: FxProvider,
    account_ids: frozenset[str] | None = None,
    as_of: str | None = None,
) -> DashboardViewModel:
    """Filter people, build a snapshot, and adapt it — the full pipeline.

    The sidebar always reflects *all* people/accounts; only the dashboard
    metrics and table are filtered by ``account_ids``.
    """
    selected = filter_people(people, account_ids)
    snapshot = build_snapshot(selected, display_currency, provider, as_of=as_of)
    view_model = build_dashboard_view_model(snapshot, provider)
    if account_ids is not None:
        view_model = DashboardViewModel(
            total_value=view_model.total_value,
            holding_count=view_model.holding_count,
            account_count=view_model.account_count,
            kpis=view_model.kpis,
            rows=view_model.rows,
            sidebar=_sidebar_from(people),
        )
    return view_model
