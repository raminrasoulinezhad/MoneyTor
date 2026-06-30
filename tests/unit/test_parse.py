# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""Tests for the loosely-typed JSON -> domain coercion helpers (connectors)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from moneytor.connectors._parse import to_currency, to_decimal, to_money
from moneytor.connectors.errors import FetchError
from moneytor.domain.enums import Currency
from moneytor.domain.money import Money

CAD = Currency.CAD


# --------------------------------------------------------------------------- #
# to_decimal
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1.50", Decimal("1.50")),
        (2, Decimal("2")),
        ("0", Decimal("0")),
        ("-3.25", Decimal("-3.25")),
    ],
)
def test_to_decimal_coerces_valid(value: object, expected: Decimal) -> None:
    assert to_decimal(value, "x") == expected


@pytest.mark.parametrize("bad", ["abc", None, "", "NaN", [1]])
def test_to_decimal_rejects_garbage(bad: object) -> None:
    with pytest.raises(FetchError, match="Invalid number at price"):
        to_decimal(bad, "price")


# --------------------------------------------------------------------------- #
# to_currency
# --------------------------------------------------------------------------- #


def test_to_currency_valid() -> None:
    assert to_currency("CAD", "x") is Currency.CAD
    assert to_currency("USD", "x") is Currency.USD


@pytest.mark.parametrize("bad", ["EUR", "cad", "", None])
def test_to_currency_rejects_unsupported(bad: object) -> None:
    with pytest.raises(FetchError, match="Unsupported currency at cash"):
        to_currency(bad, "cash")


# --------------------------------------------------------------------------- #
# to_money
# --------------------------------------------------------------------------- #


def test_to_money_parses_node() -> None:
    assert to_money({"amount": "12.34", "currency": "CAD"}, "x") == Money.of("12.34", CAD)


@pytest.mark.parametrize("node", [None, "10 CAD", ["10", "CAD"], 10])
def test_to_money_rejects_non_dict(node: object) -> None:
    with pytest.raises(FetchError, match="Expected a money object"):
        to_money(node, "holding.market_value")


def test_to_money_rejects_missing_amount() -> None:
    with pytest.raises(FetchError, match="Invalid number"):
        to_money({"currency": "CAD"}, "x")  # amount missing -> None -> invalid


def test_to_money_rejects_missing_currency() -> None:
    with pytest.raises(FetchError, match="Unsupported currency"):
        to_money({"amount": "10"}, "x")  # currency missing -> None -> unsupported
