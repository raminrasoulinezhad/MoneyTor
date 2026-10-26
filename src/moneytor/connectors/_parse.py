# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Shared helpers for mapping loosely-typed JSON into typed domain values.

``Any`` is intentional here: these inputs are external, untyped API payloads.
Each helper validates and raises :class:`FetchError` on bad data so callers map
straight into typed domain models.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from moneytor.domain.enums import AccountType, Currency
from moneytor.domain.money import Money

from .errors import FetchError

_LOG = logging.getLogger(__name__)


def to_decimal(value: Any, where: str) -> Decimal:
    """Coerce a JSON number/string to ``Decimal`` (no float path).

    Rejects non-finite values (``NaN``/``Infinity``): they parse as valid
    ``Decimal`` objects but would silently poison every downstream sum.
    """
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            raise InvalidOperation
    except (InvalidOperation, TypeError) as exc:
        raise FetchError(f"Invalid number at {where}: {value!r}.") from exc
    return result


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


def account_type_for(known: Mapping[str, AccountType], raw: Any, broker: str) -> AccountType:
    """Map a broker's account-type string, falling back to ``OTHER`` — loudly.

    An unrecognised type used to default to CASH, filing a registered account
    (a Questrade FHSA, say) as non-registered. ``OTHER`` makes no such claim,
    and the warning names the string so it can be added to the table.
    """
    account_type = known.get(str(raw))
    if account_type is None:
        _LOG.warning("Unrecognised %s account type %r; showing it as Other.", broker, raw)
        return AccountType.OTHER
    return account_type
