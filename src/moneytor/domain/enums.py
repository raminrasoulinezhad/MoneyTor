# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

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
