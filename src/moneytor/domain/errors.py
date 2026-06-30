# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""Domain-layer error types."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for errors raised by the pure domain core."""


class CurrencyMismatchError(DomainError):
    """Raised when an operation mixes two different currencies.

    Cross-currency arithmetic must go through the FX layer
    (:mod:`moneytor.fx`), never through raw ``Money`` operators.
    """
