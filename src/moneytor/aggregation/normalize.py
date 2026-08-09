# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Symbol normalization — collapse the same asset across exchanges.

A holding carries a ``symbol`` and an ``exchange`` (e.g. ``SHOP`` on ``TSX`` vs
``SHOP`` on ``NYSE``, or a suffixed ``SHOP.TO``). To merge identical assets we
reduce each ticker to a canonical form by:

1. applying explicit file-based overrides (highest priority), then
2. stripping a *known* exchange suffix (so share-class dots like ``BRK.B`` are
   preserved while ``SHOP.TO`` becomes ``SHOP``).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from moneytor.domain.enums import AssetClass
from moneytor.domain.models import Account, Person

# Suffixes that denote a listing venue (safe to strip), not a share class.
# ``VN`` is TSX Venture as some feeds spell it (alongside ``V``); like the
# others it only names the exchange, so ``ABC.VN`` collapses to ``ABC``.
KNOWN_EXCHANGE_SUFFIXES = frozenset({"TO", "V", "VN", "NE", "CN", "TSX", "TSXV", "US"})

# The 11 official GICS sectors (for reference / file-override validation).
GICS_SECTORS: tuple[str, ...] = (
    "Energy",
    "Materials",
    "Industrials",
    "Consumer Discretionary",
    "Consumer Staples",
    "Health Care",
    "Financials",
    "Information Technology",
    "Communication Services",
    "Utilities",
    "Real Estate",
)

# Map broker sector vocabularies (notably Questrade's Morningstar names) and
# common spelling variants onto canonical GICS sector names. Keys are collapsed
# (lower-cased, spaces/hyphens removed) so "Financial Services" == "financialservices".
_SECTOR_ALIASES: dict[str, str] = {
    "basicmaterials": "Materials",
    "materials": "Materials",
    "energy": "Energy",
    "industrials": "Industrials",
    "consumercyclical": "Consumer Discretionary",
    "consumerdiscretionary": "Consumer Discretionary",
    "consumerdefensive": "Consumer Staples",
    "consumerstaples": "Consumer Staples",
    "healthcare": "Health Care",
    "financialservices": "Financials",
    "financial": "Financials",
    "financials": "Financials",
    "technology": "Information Technology",
    "informationtechnology": "Information Technology",
    "communicationservices": "Communication Services",
    "communication": "Communication Services",
    "utilities": "Utilities",
    "realestate": "Real Estate",
}


def normalize_sector(raw: str) -> str:
    """Map a raw broker/file sector string onto a canonical GICS sector.

    Returns ``""`` for blank input and passes unrecognized values through
    unchanged (title-cased), so unknown classifications still display.
    """
    cleaned = raw.strip()
    if not cleaned:
        return ""
    key = cleaned.lower().replace("-", "").replace(" ", "")
    return _SECTOR_ALIASES.get(key, cleaned)


# Synthetic, non-GICS sectors used to group non-equity holdings in allocation
# views. Cash balances bucket as "Cash"; GICs as the distinct, near-cash
# "Cash-Equivalent" bucket.
CASH_SECTOR = "Cash"
CASH_EQUIVALENT_SECTOR = "Cash-Equivalent"
BULLION_SECTOR = "Bullion"

# Tickers that represent physical gold/bullion rather than a GICS-classified
# security. Add new bullion symbols here. Compared case-insensitively.
BULLION_SYMBOLS: frozenset[str] = frozenset({"GOLD", "IAUM"})


def classify_sector(symbol: str, asset_class: AssetClass, sector: str) -> str:
    """Resolve a holding's display sector, applying fixed overrides.

    Cash balances collapse into the ``"Cash"`` sector; GICs into the distinct
    ``"Cash-Equivalent"`` sector; known bullion tickers into ``"Bullion"``.
    These overrides win over any broker- or file-supplied ``sector`` because the
    asset's nature is fixed regardless of how a broker happens to classify it.
    Any other holding keeps ``sector``.
    """
    if asset_class is AssetClass.CASH:
        return CASH_SECTOR
    if asset_class is AssetClass.GIC:
        return CASH_EQUIVALENT_SECTOR
    if symbol.strip().upper() in BULLION_SYMBOLS:
        return BULLION_SECTOR
    return sector


def _strip_exchange_suffix(symbol: str) -> str:
    head, _, tail = symbol.rpartition(".")
    if head and tail in KNOWN_EXCHANGE_SUFFIXES:
        return head
    return symbol


@dataclass(frozen=True)
class AssetMap:
    """Case-insensitive ticker → canonical-symbol overrides."""

    overrides: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized = {
            key.strip().upper(): value.strip().upper() for key, value in self.overrides.items()
        }
        object.__setattr__(self, "overrides", normalized)

    @classmethod
    def from_file(cls, path: str | Path) -> AssetMap:
        """Load overrides from a JSON object file (``{"SHOP.TO": "SHOP"}``)."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Asset map {path} must be a JSON object.")
        return cls(overrides=data)

    def canonical(self, symbol: str) -> str:
        """Return the canonical symbol for ``symbol``."""
        key = symbol.strip().upper()
        if key in self.overrides:
            return self.overrides[key]
        return _strip_exchange_suffix(key)


@dataclass(frozen=True)
class SectorMap:
    """Case-insensitive ticker → GICS sector overrides.

    Used to supply sectors for holdings whose broker doesn't (e.g. Wealthsimple)
    and to override broker-provided values. Lookups are by exact ticker.
    """

    sectors: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized = {key.strip().upper(): value.strip() for key, value in self.sectors.items()}
        object.__setattr__(self, "sectors", normalized)

    @classmethod
    def from_file(cls, path: str | Path) -> SectorMap:
        """Load sectors from a JSON object file (``{"AAPL": "Information Technology"}``)."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Sector map {path} must be a JSON object.")
        return cls(sectors=data)

    def get(self, symbol: str) -> str:
        """Return the mapped (GICS-normalized) sector for ``symbol``, or ``""``."""
        return normalize_sector(self.sectors.get(symbol.strip().upper(), ""))


def apply_sector_map(people: Sequence[Person], sector_map: SectorMap) -> tuple[Person, ...]:
    """Fill in each holding's ``sector`` from ``sector_map`` where it is empty.

    Broker-supplied sectors win; the map only fills gaps. Immutable in/out.
    """
    if not sector_map.sectors:
        return tuple(people)

    def fill(account: Account) -> Account:
        holdings = tuple(
            h if h.sector else replace(h, sector=sector_map.get(h.symbol)) for h in account.holdings
        )
        return replace(account, holdings=holdings)

    return tuple(replace(p, accounts=tuple(fill(a) for a in p.accounts)) for p in people)
