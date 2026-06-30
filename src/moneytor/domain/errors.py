"""Domain-layer error types."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for errors raised by the pure domain core."""


class CurrencyMismatchError(DomainError):
    """Raised when an operation mixes two different currencies.

    Cross-currency arithmetic must go through the FX layer
    (:mod:`moneytor.fx`), never through raw ``Money`` operators.
    """
