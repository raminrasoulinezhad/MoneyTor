"""Build a PortfolioSnapshot and compute rollups/allocations.

Pure transforms over domain models. The clock is *not* read here: ``as_of`` is
supplied by the imperative shell so snapshots are deterministic.

24h change is intentionally absent until connectors supply day-change/previous-
close data (Phase 8); the model carries no such field yet.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal

from moneytor.domain.enums import AssetClass, Currency
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


def annual_dividend_income(snapshot: PortfolioSnapshot) -> Money:
    """Rough estimated yearly dividend income, in the snapshot's display currency.

    For each unified holding with a known dividend yield, the estimate is
    ``market value * yield`` (both already in the display currency). Holdings
    whose broker did not supply a yield contribute nothing, so the figure is a
    lower-bound estimate rather than an exact forward dividend.
    """
    total = Money.zero(snapshot.display_currency)
    for holding in snapshot.unified_holdings:
        if holding.dividend_yield is None:
            continue
        total += holding.total_market_value * holding.dividend_yield
    return total.quantize()


_GIC_RATE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def gic_interest_rate(text: str) -> Decimal | None:
    """Parse a GIC's annual interest rate (as a fraction) from its name/details.

    GICs carry their rate in the holding name or symbol, e.g.
    ``"Oaken GIC 4.50% 2027"`` → ``Decimal("0.045")``. The first percentage in
    the string wins. Returns None when no percentage is present.
    """
    match = _GIC_RATE_RE.search(text)
    if match is None:
        return None
    return Decimal(match.group(1)) / Decimal("100")


# GICs reach us under either asset class: a broker that exposes a dedicated GIC
# type maps to ``GIC``, but Questrade/Wealthsimple file GICs as ``Bond`` →
# ``FIXED_INCOME`` (e.g. "HOME TRUST … MAT 07/08/2026 2.55% 90D"). Both carry the
# annual rate in the holding name, so both are candidates for interest.
_INTEREST_BEARING: frozenset[AssetClass] = frozenset({AssetClass.GIC, AssetClass.FIXED_INCOME})


def annual_gic_interest(snapshot: PortfolioSnapshot) -> Money:
    """Rough estimated yearly GIC/fixed-income interest, in the display currency.

    Covers both ``GIC`` holdings and the ``FIXED_INCOME`` holdings brokers use
    for GICs/bonds. For each whose name (or symbol) encodes an annual rate, the
    estimate is ``market value * rate`` (already in the display currency).
    Holdings with no parseable rate contribute nothing, so this is a lower-bound
    estimate.
    """
    total = Money.zero(snapshot.display_currency)
    for holding in snapshot.unified_holdings:
        if holding.asset_class not in _INTEREST_BEARING:
            continue
        rate = gic_interest_rate(holding.name) or gic_interest_rate(holding.symbol)
        if rate is None:
            continue
        total += holding.total_market_value * rate
    return total.quantize()


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
