# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""Aggregation engine — pure transforms: normalize, merge, roll up."""

from __future__ import annotations

from .merge import merge_holdings
from .normalize import GICS_SECTORS, AssetMap, SectorMap, apply_sector_map, normalize_sector
from .snapshot import (
    account_value,
    allocation_by_symbol,
    annual_dividend_income,
    annual_gic_interest,
    build_snapshot,
    collect_holdings,
    gic_interest_rate,
    person_value,
    totals_by_currency,
)

__all__ = [
    "GICS_SECTORS",
    "AssetMap",
    "SectorMap",
    "account_value",
    "allocation_by_symbol",
    "annual_dividend_income",
    "annual_gic_interest",
    "apply_sector_map",
    "build_snapshot",
    "collect_holdings",
    "gic_interest_rate",
    "merge_holdings",
    "normalize_sector",
    "person_value",
    "totals_by_currency",
]
