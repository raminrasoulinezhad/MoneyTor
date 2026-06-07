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
