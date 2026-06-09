"""Tests for shared display formatting helpers."""

from __future__ import annotations

from decimal import Decimal

import pytest

from moneytor.formatting import format_quantity


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("10", "10"),  # regression: whole numbers keep trailing zeros
        ("100", "100"),
        ("25", "25"),
        ("10.50", "10.5"),  # fractional trailing zeros trimmed
        ("10.00", "10"),
        ("1234.5", "1,234.5"),  # thousands separator
        ("0.125", "0.125"),
        ("0", "0"),
    ],
)
def test_format_quantity(value: str, expected: str) -> None:
    assert format_quantity(Decimal(value)) == expected
