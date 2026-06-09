"""Aggregation engine — pure transforms: normalize, merge, roll up."""

from __future__ import annotations

from .merge import merge_holdings
from .normalize import GICS_SECTORS, AssetMap, SectorMap, apply_sector_map, normalize_sector
from .snapshot import (
    account_value,
    allocation_by_symbol,
    build_snapshot,
    collect_holdings,
    person_value,
    totals_by_currency,
)

__all__ = [
    "GICS_SECTORS",
    "AssetMap",
    "SectorMap",
    "account_value",
    "allocation_by_symbol",
    "apply_sector_map",
    "build_snapshot",
    "collect_holdings",
    "merge_holdings",
    "normalize_sector",
    "person_value",
    "totals_by_currency",
]
