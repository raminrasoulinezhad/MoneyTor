# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""Tests for the FX layer (Phase 3)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from moneytor.domain import Currency, Money
from moneytor.fx import (
    FxProvider,
    FxRateUnavailableError,
    StaticFxProvider,
    convert,
)

CAD = Currency.CAD
USD = Currency.USD

PROVIDER = StaticFxProvider(
    rates={
        (USD, CAD): Decimal("1.35"),
        (CAD, USD): Decimal("0.74"),
    }
)


def test_static_provider_satisfies_protocol() -> None:
    assert isinstance(PROVIDER, FxProvider)


def test_identity_rate_is_one() -> None:
    assert PROVIDER.get_rate(CAD, CAD) == Decimal("1")


def test_known_pair() -> None:
    assert PROVIDER.get_rate(USD, CAD) == Decimal("1.35")


def test_missing_pair_raises() -> None:
    other = StaticFxProvider(rates={})
    with pytest.raises(FxRateUnavailableError, match="USD->CAD"):
        other.get_rate(USD, CAD)


def test_convert_same_currency_is_noop() -> None:
    money = Money.of("100", CAD)
    assert convert(money, CAD, PROVIDER) is money


def test_convert_applies_rate_and_quantizes() -> None:
    result = convert(Money.of("100", USD), CAD, PROVIDER)
    assert result.currency is CAD
    assert result.amount == Decimal("135.00")


def test_convert_quantizes_to_two_places() -> None:
    # 10 USD * 1.35 = 13.5 -> 13.50; verify exponent is 2 dp
    result = convert(Money.of("10", USD), CAD, PROVIDER)
    assert result.amount == Decimal("13.50")
    assert result.amount.as_tuple().exponent == -2
