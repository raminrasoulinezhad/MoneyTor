# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

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
