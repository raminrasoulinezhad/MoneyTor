# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""FX-layer error types."""

from __future__ import annotations


class FxError(Exception):
    """Base class for currency-conversion errors."""


class FxRateUnavailableError(FxError):
    """Raised when no rate is available for a requested currency pair."""
