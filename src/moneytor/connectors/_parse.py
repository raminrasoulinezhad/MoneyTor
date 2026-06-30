# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""Shared helpers for mapping loosely-typed JSON into typed domain values.

``Any`` is intentional here: these inputs are external, untyped API payloads.
Each helper validates and raises :class:`FetchError` on bad data so callers map
straight into typed domain models.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from moneytor.domain.enums import Currency
from moneytor.domain.money import Money

from .errors import FetchError


def to_decimal(value: Any, where: str) -> Decimal:
    """Coerce a JSON number/string to ``Decimal`` (no float path)."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise FetchError(f"Invalid number at {where}: {value!r}.") from exc


def to_currency(value: Any, where: str) -> Currency:
    """Coerce a JSON value to a supported :class:`Currency`."""
    try:
        return Currency(value)
    except ValueError as exc:
        raise FetchError(f"Unsupported currency at {where}: {value!r}.") from exc


def to_money(node: Any, where: str) -> Money:
    """Parse an ``{"amount": ..., "currency": ...}`` node into ``Money``."""
    if not isinstance(node, dict):
        raise FetchError(f"Expected a money object at {where}: {node!r}.")
    return Money(to_decimal(node.get("amount"), where), to_currency(node.get("currency"), where))
