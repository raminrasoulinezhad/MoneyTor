"""Shared display formatting helpers (presentation-agnostic)."""

from __future__ import annotations

from decimal import Decimal


def format_quantity(quantity: Decimal) -> str:
    """Format a share quantity with thousands separators, trimming only
    *fractional* trailing zeros (so ``Decimal("10")`` stays ``"10"``, not
    ``"1"``, while ``Decimal("10.50")`` becomes ``"10.5"``).
    """
    text = f"{quantity:,f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text
