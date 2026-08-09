# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Shared domain enumerations.

Kept tiny and dependency-free so every layer (config, connectors, aggregation,
ui) can import them without coupling to richer domain models (Phase 3).
"""

from __future__ import annotations

from enum import StrEnum


class Currency(StrEnum):
    """Supported settlement/display currencies."""

    CAD = "CAD"
    USD = "USD"


class Institution(StrEnum):
    """Supported Canadian brokerages. Extendable."""

    WEALTHSIMPLE = "wealthsimple"
    QUESTRADE = "questrade"


class AccountType(StrEnum):
    """Registered and non-registered account types."""

    TFSA = "tfsa"
    RRSP = "rrsp"
    SPOUSAL_RRSP = "spousal_rrsp"
    FHSA = "fhsa"
    MARGIN = "margin"
    MANAGED = "managed"
    GIC = "gic"
    CASH = "cash"


class AssetClass(StrEnum):
    """Broad asset classification for a holding."""

    EQUITY = "equity"
    ETF = "etf"
    CASH = "cash"
    GIC = "gic"
    FIXED_INCOME = "fixed_income"
    CRYPTO = "crypto"
    OTHER = "other"
