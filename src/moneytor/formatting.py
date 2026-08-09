# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Shared display formatting helpers (presentation-agnostic)."""

from __future__ import annotations

from decimal import Decimal

# Placeholder shown in place of sensitive monetary values when private mode is on.
PRIVATE_MASK = "••••••"


def format_quantity(quantity: Decimal) -> str:
    """Format a share quantity with thousands separators, trimming only
    *fractional* trailing zeros (so ``Decimal("10")`` stays ``"10"``, not
    ``"1"``, while ``Decimal("10.50")`` becomes ``"10.5"``).
    """
    text = f"{quantity:,f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


# Display overrides for asset-class labels (the value is the enum's .value).
_ASSET_CLASS_LABELS = {"fixed_income": "Cash"}


def format_asset_class(asset_class: str) -> str:
    """Human label for a holding's asset class (fixed income shown as 'Cash')."""
    return _ASSET_CLASS_LABELS.get(asset_class, asset_class.replace("_", " ").title())
