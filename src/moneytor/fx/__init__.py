# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

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
