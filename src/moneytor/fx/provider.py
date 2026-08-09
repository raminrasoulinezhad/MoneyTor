# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""FX rate providers.

The :class:`FxProvider` protocol decouples conversion from rate *sourcing*. A
static, dict-backed provider serves development and tests now; live providers
(API-backed, Phase 8) implement the same protocol without touching the pure
conversion code in :mod:`moneytor.fx.convert`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable

from moneytor.domain.enums import Currency

from .errors import FxRateUnavailableError

_ONE = Decimal(1)


@runtime_checkable
class FxProvider(Protocol):
    """Supplies the rate to convert one unit of ``base`` into ``quote``."""

    def get_rate(self, base: Currency, quote: Currency) -> Decimal:
        """Return the ``base`` → ``quote`` exchange rate.

        Implementations must return ``1`` when ``base is quote`` and raise
        :class:`FxRateUnavailableError` when no rate exists.
        """


@dataclass(frozen=True)
class StaticFxProvider:
    """An :class:`FxProvider` backed by an explicit rate table.

    Rates are looked up exactly (no automatic inverse derivation) so every
    conversion is auditable. Same-currency lookups always yield ``1``.
    """

    rates: Mapping[tuple[Currency, Currency], Decimal]

    def get_rate(self, base: Currency, quote: Currency) -> Decimal:
        if base is quote:
            return _ONE
        try:
            return self.rates[(base, quote)]
        except KeyError as exc:
            raise FxRateUnavailableError(f"No FX rate for {base.value}->{quote.value}.") from exc
