# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

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
