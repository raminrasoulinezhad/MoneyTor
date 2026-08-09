# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Domain-layer error types."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for errors raised by the pure domain core."""


class CurrencyMismatchError(DomainError):
    """Raised when an operation mixes two different currencies.

    Cross-currency arithmetic must go through the FX layer
    (:mod:`moneytor.fx`), never through raw ``Money`` operators.
    """
