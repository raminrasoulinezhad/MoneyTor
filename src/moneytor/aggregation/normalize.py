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
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from moneytor.domain.enums import AssetClass, Currency
from moneytor.domain.models import Account, Holding, Person

# Suffixes that denote a listing venue (safe to strip), not a share class.
# ``VN`` is TSX Venture as some feeds spell it (alongside ``V``); like the
# others it only names the exchange, so ``ABC.VN`` collapses to ``ABC``.
KNOWN_EXCHANGE_SUFFIXES = frozenset({"TO", "V", "VN", "NE", "CN", "TSX", "TSXV", "US"})

# Listing venue -> the currency that venue quotes in. Brokers differ on whether
# a holding's reported currency is the security's own or one they converted to
# for us (Wealthsimple asks for CAD across the board), so the exchange is the
# only trustworthy signal of what a *quote* for that security is denominated in.
# Keys are compared upper-cased with punctuation collapsed to spaces.
_EXCHANGE_CURRENCIES: dict[str, Currency] = {
    "NYSE": Currency.USD,
    "NYSE ARCA": Currency.USD,
    "NYSE AMERICAN": Currency.USD,
    "NASDAQ": Currency.USD,
    "AMEX": Currency.USD,
    "ARCA": Currency.USD,
    "BATS": Currency.USD,
    "OTC": Currency.USD,
    "TSX": Currency.CAD,
    "TSX V": Currency.CAD,
    "TSXV": Currency.CAD,
    "TSX VENTURE": Currency.CAD,
    "CSE": Currency.CAD,
    "NEO": Currency.CAD,
    "CBOE CANADA": Currency.CAD,
    "AEQUITAS NEO": Currency.CAD,
}


def currency_for_exchange(exchange: str) -> Currency | None:
    """The currency ``exchange`` quotes in, or None when it is unknown/blank.

    Unknown venues deliberately return None rather than guessing a default, so
    callers fall back to whatever the broker reported instead of relabelling a
    value with a currency it may not be in.
    """
    if not exchange:
        return None
    key = re.sub(r"[^A-Z0-9]+", " ", exchange.upper()).strip()
    return _EXCHANGE_CURRENCIES.get(key)


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
    "material": "Materials",
    "materials": "Materials",
    "energy": "Energy",
    "industrial": "Industrials",
    "industrials": "Industrials",
    "consumercyclical": "Consumer Discretionary",
    "consumerdiscretionary": "Consumer Discretionary",
    "consumerdefensive": "Consumer Staples",
    "consumerstaple": "Consumer Staples",
    "consumerstaples": "Consumer Staples",
    "healthcare": "Health Care",
    "healthcareservices": "Health Care",
    "financialservices": "Financials",
    "financial": "Financials",
    "financials": "Financials",
    "technology": "Information Technology",
    "informationtechnology": "Information Technology",
    "communicationservices": "Communication Services",
    "communication": "Communication Services",
    "utility": "Utilities",
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
# views, so nothing a broker can hand us falls through as a blank sector.
CASH_SECTOR = "Cash"
CASH_EQUIVALENT_SECTOR = "Cash-Equivalent"  # GICs and other near-cash paper
BULLION_SECTOR = "Bullion"
CRYPTO_SECTOR = "Crypto"
COMMODITY_SECTOR = "Commodities"  # broad commodity funds, assigned by ticker

# Tickers that represent physical gold/bullion rather than a GICS-classified
# security. Add new bullion symbols here. Compared case-insensitively.
BULLION_SYMBOLS: frozenset[str] = frozenset({"GOLD", "IAUM"})

# Coins a broker may hand us as a plain "other" security rather than tagging
# them CRYPTO. Compared case-insensitively.
CRYPTO_SYMBOLS: frozenset[str] = frozenset({"BTC", "ETH", "SOL", "XRP", "DOGE", "LTC", "ADA"})

# Asset classes that always carry a synthetic sector, whatever the broker said.
# Brokers without a dedicated GIC type file GICs as a bond (see
# ``_INTEREST_BEARING`` in aggregation.snapshot), so FIXED_INCOME buckets with
# GIC rather than being left blank.
_CLASS_SECTORS: dict[AssetClass, str] = {
    AssetClass.CASH: CASH_SECTOR,
    AssetClass.GIC: CASH_EQUIVALENT_SECTOR,
    AssetClass.FIXED_INCOME: CASH_EQUIVALENT_SECTOR,
    AssetClass.CRYPTO: CRYPTO_SECTOR,
}


def classify_sector(symbol: str, asset_class: AssetClass, sector: str) -> str:
    """Resolve a holding's display sector, applying fixed overrides.

    Cash balances collapse into ``"Cash"``; GICs and other fixed income into the
    distinct ``"Cash-Equivalent"``; known bullion and coin tickers into
    ``"Bullion"`` and ``"Crypto"``. These win over any broker- or file-supplied
    ``sector`` because the asset's nature is fixed regardless of how a broker
    happens to classify it. Any other holding keeps ``sector``.
    """
    fixed = _CLASS_SECTORS.get(asset_class)
    if fixed is not None:
        return fixed
    key = symbol.strip().upper()
    if key in BULLION_SYMBOLS:
        return BULLION_SECTOR
    if key in CRYPTO_SYMBOLS:
        return CRYPTO_SECTOR
    return sector


def _strip_exchange_suffix(symbol: str) -> str:
    head, _, tail = symbol.rpartition(".")
    if head and tail in KNOWN_EXCHANGE_SUFFIXES:
        return head
    return symbol


def base_ticker(symbol: str) -> str:
    """``symbol`` upper-cased, without a listing-venue suffix (``cve.to`` → ``CVE``)."""
    return _strip_exchange_suffix(symbol.strip().upper())


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

    @classmethod
    def from_groups(cls, groups: Iterable[Sequence[str]]) -> AssetMap:
        """Map every ticker in each group onto the group's first ticker.

        ``[["CCO", "CCJ"]]`` merges Cameco's two listings under ``CCO``. A
        ticker named in two groups keeps its first, so a later group (the
        user's file, say) cannot silently split an earlier one.
        """
        overrides: dict[str, str] = {}
        for group in groups:
            tickers = [base_ticker(t) for t in group if t.strip()]
            if len(tickers) < 2:
                continue
            for ticker in tickers:
                overrides.setdefault(ticker, tickers[0])
        return cls(overrides=overrides)

    @classmethod
    def groups_from_file(cls, path: str | Path) -> list[list[str]]:
        """Read listing groups from a JSON file (``[["CCO", "CCJ"], ...]``)."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        valid = isinstance(data, list) and all(
            isinstance(g, list) and all(isinstance(t, str) for t in g) for g in data
        )
        if not valid:
            raise ValueError(f"Listing groups {path} must be a JSON list of lists of tickers.")
        return [[str(t) for t in group] for group in data]

    def canonical(self, symbol: str) -> str:
        """Return the canonical symbol for ``symbol``.

        Looked up as given, then without its exchange suffix, so a group entry
        for ``CCJ`` also catches a broker reporting ``CCJ.US``.
        """
        key = symbol.strip().upper()
        if key in self.overrides:
            return self.overrides[key]
        base = _strip_exchange_suffix(key)
        return self.overrides.get(base, base)


@dataclass(frozen=True)
class SectorMap:
    """Case-insensitive ticker → GICS sector overrides.

    Used to supply sectors for holdings whose broker doesn't (e.g. Wealthsimple)
    and to override broker-provided values. Keys may carry an exchange suffix
    or not — ``"CVE"`` and ``"CVE.TO"`` resolve to the same holding.
    """

    sectors: Mapping[str, str] = field(default_factory=dict)
    # Derived: the same entries re-keyed without their exchange suffix, so a
    # lookup matches whichever form the broker and the file happen to use.
    _by_canonical: Mapping[str, str] = field(
        init=False, repr=False, compare=False, default_factory=dict
    )

    def __post_init__(self) -> None:
        normalized = {key.strip().upper(): value.strip() for key, value in self.sectors.items()}
        object.__setattr__(self, "sectors", normalized)
        canonical: dict[str, str] = {}
        for key, value in normalized.items():
            canonical.setdefault(_strip_exchange_suffix(key), value)
        object.__setattr__(self, "_by_canonical", canonical)

    @classmethod
    def from_file(cls, path: str | Path) -> SectorMap:
        """Load sectors from a JSON object file (``{"AAPL": "Information Technology"}``)."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Sector map {path} must be a JSON object.")
        return cls(sectors=data)

    def get(self, symbol: str) -> str:
        """Return the mapped (GICS-normalized) sector for ``symbol``, or ``""``.

        Looked up by exact ticker first, then by the canonical form
        :meth:`AssetMap.canonical` uses, on both sides — so ``"CVE"`` and
        ``"CVE.TO"`` each match a holding reported either way. Without that
        fallback an override silently did nothing for a suffixed ticker, which
        is exactly how the brokers report Canadian listings.
        """
        key = symbol.strip().upper()
        mapped = self.sectors.get(key) or self._by_canonical.get(_strip_exchange_suffix(key), "")
        return normalize_sector(mapped)


def apply_sector_map(people: Sequence[Person], sector_map: SectorMap) -> tuple[Person, ...]:
    """Give every holding a normalized sector, in strict precedence order.

    For each holding the sector is the first of:

    1. its own broker-reported sector, normalized;
    2. a broker-reported sector for the *same* canonical ticker held elsewhere —
       Questrade classifies, Wealthsimple does not, so one account's data fills
       the other's gap;
    3. the ``sector_map`` entry (bundled defaults plus the user's file).

    Resolving step 2 across the whole portfolio matters: :func:`merge_holdings`
    takes the first non-empty sector among a symbol's sources, so without it a
    map value filled into one account could outrank real broker data in another
    purely on ordering. Immutable in/out.
    """
    known: dict[str, str] = {}
    for person in people:
        for account in person.accounts:
            for holding in account.holdings:
                sector = normalize_sector(holding.sector)
                if sector:
                    known.setdefault(_strip_exchange_suffix(holding.symbol.strip().upper()), sector)

    def resolve(holding: Holding) -> Holding:
        key = _strip_exchange_suffix(holding.symbol.strip().upper())
        sector = normalize_sector(holding.sector) or known.get(key) or sector_map.get(key)
        return holding if sector == holding.sector else replace(holding, sector=sector)

    def fill(account: Account) -> Account:
        return replace(account, holdings=tuple(resolve(h) for h in account.holdings))

    return tuple(replace(p, accounts=tuple(fill(a) for a in p.accounts)) for p in people)
