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
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

# Suffixes that denote a listing venue (safe to strip), not a share class.
KNOWN_EXCHANGE_SUFFIXES = frozenset({"TO", "V", "NE", "CN", "TSX", "TSXV", "US"})


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
