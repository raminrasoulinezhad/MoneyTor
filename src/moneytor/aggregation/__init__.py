"""Aggregation engine — pure transforms: normalize, merge, roll up."""

from __future__ import annotations

from .merge import merge_holdings
from .normalize import AssetMap
from .snapshot import (
    account_value,
    allocation_by_symbol,
    build_snapshot,
    collect_holdings,
    person_value,
    totals_by_currency,
)

__all__ = [
    "AssetMap",
    "account_value",
    "allocation_by_symbol",
    "build_snapshot",
    "collect_holdings",
    "merge_holdings",
    "person_value",
    "totals_by_currency",
]
