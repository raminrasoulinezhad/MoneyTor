"""Core domain models — the contract every other layer consumes.

All models are frozen (immutable) and fully typed. They hold *normalized* data:
connectors map raw broker payloads into these (Phase 4), and the aggregation
engine transforms them into unified views and snapshots (Phase 5).

The pure core never reads the clock — ``PortfolioSnapshot.as_of`` is supplied
by the imperative shell so transformations stay deterministic and testable.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from functools import reduce

from .enums import AccountType, AssetClass, Currency, Institution
from .money import Money


@dataclass(frozen=True)
class Holding:
    """A single position within one account, as reported by one institution."""

    symbol: str
    exchange: str
    asset_class: AssetClass
    quantity: Decimal
    book_value: Money
    market_value: Money
    name: str = ""  # human-readable company/fund name, when the broker supplies it
    sector: str = ""  # GICS sector, when known (broker-supplied or file override)
    high_52w: Money | None = None  # 52-week-high price per share (native currency)


@dataclass(frozen=True)
class Account:
    """One account belonging to a person at an institution."""

    id: str
    person_id: str
    institution: Institution
    account_type: AccountType
    cash: Money
    holdings: tuple[Holding, ...] = field(default_factory=tuple)

    def market_value(self) -> Money:
        """Total market value of holdings + cash, in this account's currency.

        Same-currency rollup only. Cross-currency totals require FX and belong
        to the aggregation engine (Phase 5); this raises
        :class:`~moneytor.domain.errors.CurrencyMismatchError` on a mix.
        """
        return reduce(
            lambda acc, h: acc + h.market_value,
            self.holdings,
            self.cash,
        )


@dataclass(frozen=True)
class Person:
    """A family member with one or more accounts."""

    id: str
    name: str
    accounts: tuple[Account, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class UnifiedHolding:
    """Identical asset merged across exchanges/accounts (built in Phase 5)."""

    symbol: str
    asset_class: AssetClass
    total_quantity: Decimal
    total_market_value: Money
    sources: tuple[Holding, ...] = field(default_factory=tuple)
    name: str = ""
    sector: str = ""
    high_52w: Money | None = None


@dataclass(frozen=True)
class PortfolioSnapshot:
    """Top-level aggregated view rendered by the GUI/reporting layers."""

    display_currency: Currency
    totals_by_currency: Mapping[Currency, Money]
    people: tuple[Person, ...] = field(default_factory=tuple)
    unified_holdings: tuple[UnifiedHolding, ...] = field(default_factory=tuple)
    as_of: str | None = None
