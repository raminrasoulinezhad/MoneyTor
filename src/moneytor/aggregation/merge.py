"""Merge identical assets across exchanges/accounts into unified holdings."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal

from moneytor.domain.enums import Currency
from moneytor.domain.models import Holding, UnifiedHolding
from moneytor.domain.money import Money
from moneytor.fx.convert import convert
from moneytor.fx.provider import FxProvider

from .normalize import AssetMap, classify_sector


def merge_holdings(
    holdings: Sequence[Holding],
    target_currency: Currency,
    provider: FxProvider,
    asset_map: AssetMap | None = None,
) -> tuple[UnifiedHolding, ...]:
    """Group holdings by canonical symbol and merge each group.

    Quantities are summed; market values are FX-converted to
    ``target_currency`` and summed. Result is sorted by symbol for determinism,
    making the operation order-independent (commutative).
    """
    asset_map = asset_map or AssetMap()
    groups: dict[str, list[Holding]] = defaultdict(list)
    for holding in holdings:
        groups[asset_map.canonical(holding.symbol)].append(holding)

    unified: list[UnifiedHolding] = []
    for symbol in sorted(groups):
        members = groups[symbol]
        total_quantity = sum((h.quantity for h in members), Decimal("0"))
        total_value = Money.zero(target_currency)
        for holding in members:
            total_value += convert(holding.market_value, target_currency, provider)
        asset_class = members[0].asset_class
        raw_sector = next((m.sector for m in members if m.sector), "")
        unified.append(
            UnifiedHolding(
                symbol=symbol,
                asset_class=asset_class,
                total_quantity=total_quantity,
                total_market_value=total_value.quantize(),
                sources=tuple(members),
                name=next((m.name for m in members if m.name), ""),
                sector=classify_sector(symbol, asset_class, raw_sector),
                high_52w=next((m.high_52w for m in members if m.high_52w is not None), None),
                dividend_yield=next(
                    (m.dividend_yield for m in members if m.dividend_yield is not None), None
                ),
            )
        )
    return tuple(unified)
