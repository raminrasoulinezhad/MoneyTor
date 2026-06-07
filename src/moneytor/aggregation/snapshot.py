"""Build a PortfolioSnapshot and compute rollups/allocations.

Pure transforms over domain models. The clock is *not* read here: ``as_of`` is
supplied by the imperative shell so snapshots are deterministic.

24h change is intentionally absent until connectors supply day-change/previous-
close data (Phase 8); the model carries no such field yet.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from moneytor.domain.enums import Currency
from moneytor.domain.models import Account, Holding, Person, PortfolioSnapshot
from moneytor.domain.money import Money
from moneytor.fx.convert import convert
from moneytor.fx.provider import FxProvider

from .merge import merge_holdings
from .normalize import AssetMap


def collect_holdings(people: Sequence[Person]) -> tuple[Holding, ...]:
    """Flatten every holding across all people and accounts."""
    return tuple(
        holding for person in people for account in person.accounts for holding in account.holdings
    )


def totals_by_currency(people: Sequence[Person]) -> dict[Currency, Money]:
    """Sum holdings + cash grouped by their native currency (no conversion)."""
    totals: dict[Currency, Money] = {}

    def add(money: Money) -> None:
        current = totals.get(money.currency, Money.zero(money.currency))
        totals[money.currency] = current + money

    for person in people:
        for account in person.accounts:
            add(account.cash)
            for holding in account.holdings:
                add(holding.market_value)
    return totals


def account_value(account: Account, target: Currency, provider: FxProvider) -> Money:
    """Total value of an account in ``target`` currency (FX-converted)."""
    total = convert(account.cash, target, provider)
    for holding in account.holdings:
        total += convert(holding.market_value, target, provider)
    return total.quantize()


def person_value(person: Person, target: Currency, provider: FxProvider) -> Money:
    """Total value of a person's accounts in ``target`` currency."""
    total = Money.zero(target)
    for account in person.accounts:
        total += account_value(account, target, provider)
    return total.quantize()


def allocation_by_symbol(snapshot: PortfolioSnapshot, *, places: int = 4) -> dict[str, Decimal]:
    """Fraction of total unified market value held in each symbol (sums to ~1).

    All unified holdings are already in the snapshot's display currency.
    """
    total = sum(
        (u.total_market_value.amount for u in snapshot.unified_holdings),
        Decimal("0"),
    )
    if total == 0:
        return {u.symbol: Decimal("0") for u in snapshot.unified_holdings}
    exp = Decimal(1).scaleb(-places)
    return {
        u.symbol: (u.total_market_value.amount / total).quantize(exp)
        for u in snapshot.unified_holdings
    }


def build_snapshot(
    people: Sequence[Person],
    display_currency: Currency,
    provider: FxProvider,
    asset_map: AssetMap | None = None,
    as_of: str | None = None,
) -> PortfolioSnapshot:
    """Aggregate people's portfolios into a :class:`PortfolioSnapshot`."""
    holdings = collect_holdings(people)
    unified = merge_holdings(holdings, display_currency, provider, asset_map)
    return PortfolioSnapshot(
        display_currency=display_currency,
        totals_by_currency=totals_by_currency(people),
        people=tuple(people),
        unified_holdings=unified,
        as_of=as_of,
    )
