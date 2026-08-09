# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Tests for the Money value object (Phase 3)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from moneytor.domain import Currency, CurrencyMismatchError, Money

CAD = Currency.CAD
USD = Currency.USD

# --------------------------------------------------------------------------- #
# Construction
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("value", [Decimal("1.50"), "1.50", 2, "0"])
def test_accepts_decimal_int_str(value: object) -> None:
    money = Money.of(value, CAD)  # type: ignore[arg-type]
    assert isinstance(money.amount, Decimal)


@pytest.mark.parametrize("bad", [1.50, 0.1])
def test_rejects_float(bad: float) -> None:
    with pytest.raises(TypeError, match="float"):
        Money.of(bad, CAD)  # type: ignore[arg-type]


def test_rejects_bool() -> None:
    with pytest.raises(TypeError, match="bool"):
        Money.of(True, CAD)  # type: ignore[arg-type]


def test_zero() -> None:
    assert Money.zero(USD).amount == Decimal("0")
    assert Money.zero(USD).currency is USD


def test_is_immutable() -> None:
    money = Money.of("5", CAD)
    with pytest.raises(FrozenInstanceError):
        money.amount = Decimal("6")  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Arithmetic
# --------------------------------------------------------------------------- #


def test_add_and_sub_same_currency() -> None:
    assert (Money.of("10", CAD) + Money.of("2.50", CAD)).amount == Decimal("12.50")
    assert (Money.of("10", CAD) - Money.of("2.50", CAD)).amount == Decimal("7.50")


def test_add_mixed_currency_raises() -> None:
    with pytest.raises(CurrencyMismatchError):
        _ = Money.of("10", CAD) + Money.of("10", USD)


def test_sub_mixed_currency_raises() -> None:
    with pytest.raises(CurrencyMismatchError):
        _ = Money.of("10", CAD) - Money.of("10", USD)


def test_scalar_multiplication_both_sides() -> None:
    assert (Money.of("3", CAD) * 4).amount == Decimal("12")
    assert (Decimal("1.5") * Money.of("2", CAD)).amount == Decimal("3.0")


def test_multiplication_rejects_float() -> None:
    with pytest.raises(TypeError):
        _ = Money.of("3", CAD) * 1.5  # type: ignore[operator]


def test_negation() -> None:
    assert (-Money.of("3", CAD)).amount == Decimal("-3")


# --------------------------------------------------------------------------- #
# Comparisons
# --------------------------------------------------------------------------- #


def test_comparisons_same_currency() -> None:
    assert Money.of("1", CAD) < Money.of("2", CAD)
    assert Money.of("2", CAD) >= Money.of("2", CAD)


def test_comparison_mixed_currency_raises() -> None:
    with pytest.raises(CurrencyMismatchError):
        _ = Money.of("1", CAD) < Money.of("2", USD)


def test_equality_does_not_raise_across_currencies() -> None:
    assert Money.of("1", CAD) != Money.of("1", USD)
    assert Money.of("1", CAD) == Money.of("1", CAD)


# --------------------------------------------------------------------------- #
# Rounding (banker's / ROUND_HALF_EVEN) & formatting
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2.675", "2.68"),  # rounds to even (8)
        ("2.665", "2.66"),  # rounds to even (6)
        ("2.665000", "2.66"),
        ("1.005", "1.00"),  # exact decimal -> down to even
    ],
)
def test_bankers_rounding(raw: str, expected: str) -> None:
    assert Money.of(raw, CAD).quantize().amount == Decimal(expected)


def test_format_positive() -> None:
    assert Money.of("1234.5", CAD).format() == "$1,234.50 CAD"


def test_format_negative() -> None:
    assert Money.of("-1234.567", USD).format() == "-$1,234.57 USD"


def test_str_matches_format() -> None:
    money = Money.of("12.3", CAD)
    assert str(money) == money.format()


def test_format_without_currency_code() -> None:
    assert Money.of("1234.5", CAD).format(with_currency=False) == "$1,234.50"
    assert Money.of("-50", USD).format(with_currency=False) == "-$50.00"


# --------------------------------------------------------------------------- #
# Construction — type rejection (the remaining guards)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("bad", [None, [1], {"a": 1}, (1,)])
def test_rejects_unsupported_amount_types(bad: object) -> None:
    with pytest.raises(TypeError, match="Unsupported amount type"):
        Money(bad, CAD)  # type: ignore[arg-type]


def test_rejects_non_currency() -> None:
    with pytest.raises(TypeError, match="must be a Currency"):
        Money(Decimal("1"), "CAD")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Comparisons — the <= and > operators and their currency guards
# --------------------------------------------------------------------------- #


def test_le_and_gt_same_currency() -> None:
    assert Money.of("2", CAD) <= Money.of("2", CAD)
    assert Money.of("1", CAD) <= Money.of("2", CAD)
    assert Money.of("3", CAD) > Money.of("2", CAD)
    assert not (Money.of("2", CAD) > Money.of("2", CAD))


@pytest.mark.parametrize("op", ["le", "gt"])
def test_le_gt_mixed_currency_raises(op: str) -> None:
    import operator

    with pytest.raises(CurrencyMismatchError):
        getattr(operator, op)(Money.of("1", CAD), Money.of("1", USD))


# --------------------------------------------------------------------------- #
# Arithmetic edge cases
# --------------------------------------------------------------------------- #


def test_multiply_by_zero_and_negative() -> None:
    assert (Money.of("100", CAD) * 0).amount == Decimal("0")
    assert (Money.of("100", CAD) * -1).amount == Decimal("-100")
    assert (Money.of("100", CAD) * Decimal("-0.5")).amount == Decimal("-50.0")


def test_subtraction_crossing_zero() -> None:
    assert (Money.of("2", CAD) - Money.of("5", CAD)).amount == Decimal("-3")


def test_zero_is_additive_identity() -> None:
    assert (Money.zero(CAD) + Money.of("-100", CAD)).amount == Decimal("-100")
    assert Money.zero(CAD).format() == "$0.00 CAD"


# --------------------------------------------------------------------------- #
# Rounding & formatting with non-default places
# --------------------------------------------------------------------------- #


def test_quantize_negative_uses_bankers_rounding() -> None:
    # -2.675 -> -2.68 (round half to even, away from zero here)
    assert Money.of("-2.675", CAD).quantize().amount == Decimal("-2.68")


@pytest.mark.parametrize(
    ("places", "expected"),
    [(0, Decimal("0")), (1, Decimal("0.3")), (4, Decimal("0.3333"))],
)
def test_quantize_respects_places(places: int, expected: Decimal) -> None:
    third = Decimal(1) / Decimal(3)  # 0.333... -> 0, 0.3, 0.3333 at 0/1/4 places
    assert Money(third, CAD).quantize(places).amount == expected


def test_format_with_non_default_places() -> None:
    # places=0 rounds to the nearest dollar and shows no decimals.
    assert Money.of("1234.5678", CAD).format(places=0) == "$1,235 CAD"
    assert Money.of("1.5", CAD).format(places=4) == "$1.5000 CAD"
