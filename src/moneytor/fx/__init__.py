"""Currency conversion layer."""

from __future__ import annotations

from .convert import convert
from .errors import FxError, FxRateUnavailableError
from .live import SnapshotFxProvider, fetch_usd_cad, usd_cad_table
from .provider import FxProvider, StaticFxProvider

__all__ = [
    "FxError",
    "FxProvider",
    "FxRateUnavailableError",
    "SnapshotFxProvider",
    "StaticFxProvider",
    "convert",
    "fetch_usd_cad",
    "usd_cad_table",
]
