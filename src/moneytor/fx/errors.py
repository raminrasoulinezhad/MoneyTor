"""FX-layer error types."""

from __future__ import annotations


class FxError(Exception):
    """Base class for currency-conversion errors."""


class FxRateUnavailableError(FxError):
    """Raised when no rate is available for a requested currency pair."""
