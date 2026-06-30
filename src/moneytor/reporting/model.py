# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""A render-agnostic report model built from a PortfolioSnapshot.

Both the Markdown and PDF renderers consume this, so the two outputs stay in
sync. It reuses the aggregation engine for all math and has no dependency on
the GUI layer.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from moneytor.aggregation import (
    account_value,
    allocation_by_symbol,
    person_value,
    totals_by_currency,
)
from moneytor.domain.enums import Currency
from moneytor.domain.models import PortfolioSnapshot
from moneytor.domain.money import Money
from moneytor.fx.provider import FxProvider


@dataclass(frozen=True)
class AccountLine:
    label: str
    value: Money


@dataclass(frozen=True)
class PersonLine:
    name: str
    value: Money
    accounts: tuple[AccountLine, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class HoldingLine:
    symbol: str
    asset_class: str
    quantity: Decimal
    value: Money
    allocation: Decimal  # fraction 0..1
    name: str = ""
    sector: str = ""


@dataclass(frozen=True)
class ReportModel:
    title: str
    as_of: str | None
    display_currency: Currency
    total_value: Money
    totals_by_currency: Mapping[Currency, Money]
    people: tuple[PersonLine, ...]
    holdings: tuple[HoldingLine, ...]


def build_report(
    snapshot: PortfolioSnapshot,
    provider: FxProvider,
    *,
    title: str = "MoneyTor Portfolio Report",
) -> ReportModel:
    """Compute a :class:`ReportModel` from a snapshot."""
    currency = snapshot.display_currency
    total = Money.zero(currency)
    people: list[PersonLine] = []
    for person in snapshot.people:
        value = person_value(person, currency, provider)
        total += value
        people.append(
            PersonLine(
                name=person.name,
                value=value,
                accounts=tuple(
                    AccountLine(
                        label=f"{a.account_type.value.upper()} · {a.institution.value}",
                        value=account_value(a, currency, provider),
                    )
                    for a in person.accounts
                ),
            )
        )

    allocations = allocation_by_symbol(snapshot)
    holdings = tuple(
        sorted(
            (
                HoldingLine(
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
            key=lambda h: h.value.amount,
            reverse=True,
        )
    )

    return ReportModel(
        title=title,
        as_of=snapshot.as_of,
        display_currency=currency,
        total_value=total.quantize(),
        totals_by_currency=totals_by_currency(snapshot.people),
        people=tuple(people),
        holdings=holdings,
    )
