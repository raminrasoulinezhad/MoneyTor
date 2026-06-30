# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""FX-layer error types."""

from __future__ import annotations


class FxError(Exception):
    """Base class for currency-conversion errors."""


class FxRateUnavailableError(FxError):
    """Raised when no rate is available for a requested currency pair."""
