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
