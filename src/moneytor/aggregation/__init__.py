# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

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
