# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Tests for the domain models (Phase 3)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from moneytor.domain import (
    Account,
    AccountType,
    AssetClass,
    Currency,
    CurrencyMismatchError,
    Holding,
    Institution,
    Money,
)

CAD = Currency.CAD
USD = Currency.USD


def _holding(symbol: str, currency: Currency, market: str) -> Holding:
    return Holding(
        symbol=symbol,
        exchange="TSX",
        asset_class=AssetClass.EQUITY,
        quantity=Decimal("10"),
        book_value=Money.of("100", currency),
        market_value=Money.of(market, currency),
    )


def _account(currency: Currency, holdings: tuple[Holding, ...]) -> Account:
    return Account(
        id="acct-1",
        person_id="ramin",
        institution=Institution.QUESTRADE,
        account_type=AccountType.TFSA,
        cash=Money.of("50", currency),
        holdings=holdings,
    )


def test_models_are_frozen() -> None:
    holding = _holding("SHOP", CAD, "200")
    with pytest.raises(FrozenInstanceError):
        holding.symbol = "X"  # type: ignore[misc]


def test_account_market_value_same_currency_rollup() -> None:
    account = _account(CAD, (_holding("SHOP", CAD, "200"), _holding("VFV", CAD, "300")))
    # cash 50 + 200 + 300
    assert account.market_value() == Money.of("550", CAD)


def test_account_with_no_holdings_returns_cash() -> None:
    account = _account(CAD, ())
    assert account.market_value() == Money.of("50", CAD)


def test_account_market_value_mixed_currency_raises() -> None:
    account = _account(CAD, (_holding("SHOP", CAD, "200"), _holding("AAPL", USD, "300")))
    with pytest.raises(CurrencyMismatchError):
        account.market_value()
