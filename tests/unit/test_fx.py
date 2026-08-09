# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

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


def test_convert_negative_amount() -> None:
    # A negative balance (e.g. a margin debit) converts and keeps its sign.
    result = convert(Money.of("-100", USD), CAD, PROVIDER)
    assert result == Money.of("-135.00", CAD)


def test_convert_rounds_sub_cent_with_bankers() -> None:
    # 0.01 USD * 1.35 = 0.0135 -> 0.01 (third decimal 3 rounds down).
    assert convert(Money.of("0.01", USD), CAD, PROVIDER).amount == Decimal("0.01")


def test_convert_round_trip_reflects_rate_asymmetry() -> None:
    # 1.35 and 0.74 are not exact inverses, so a round-trip is lossy by design.
    cad = convert(Money.of("100", USD), CAD, PROVIDER)
    back = convert(cad, USD, PROVIDER)
    assert back == Money.of("99.90", USD)  # 135.00 * 0.74


def test_missing_inverse_rate_is_not_auto_derived() -> None:
    # Only USD->CAD is in the table; the reverse must be supplied explicitly.
    one_way = StaticFxProvider(rates={(USD, CAD): Decimal("1.35")})
    assert one_way.get_rate(USD, CAD) == Decimal("1.35")
    with pytest.raises(FxRateUnavailableError, match="CAD->USD"):
        one_way.get_rate(CAD, USD)
