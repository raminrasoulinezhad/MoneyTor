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
    build_snapshot,
    person_value,
)
from moneytor.domain.enums import Currency
from moneytor.domain.models import Person, PortfolioSnapshot
from moneytor.domain.money import Money
from moneytor.fx.provider import FxProvider


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

    @property
    def allocation_pct(self) -> str:
        return f"{self.allocation * 100:.1f}%"


@dataclass(frozen=True)
class KpiModel:
    """A single KPI card's content."""

    title: str
    value: str
    subtitle: str = ""
    tone: str = "neutral"  # neutral | positive | negative


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
                )
                for u in snapshot.unified_holdings
            ),
            key=lambda r: r.value.amount,
            reverse=True,
        )
    )

    account_count = sum(len(p.accounts) for p in snapshot.people)
    top = rows[0] if rows else None
    kpis = (
        KpiModel("Total Portfolio Value", total.format(), f"in {currency.value}"),
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
