# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""Pure currency conversion built on an injected :class:`FxProvider`."""

from __future__ import annotations

from moneytor.domain.enums import Currency
from moneytor.domain.money import Money

from .provider import FxProvider


def convert(money: Money, target: Currency, provider: FxProvider) -> Money:
    """Convert ``money`` into ``target`` currency using ``provider``.

    A no-op (returning the original value) when already in ``target``. The
    result is quantized to 2 decimal places with banker's rounding.
    """
    if money.currency is target:
        return money
    rate = provider.get_rate(money.currency, target)
    return Money(money.amount * rate, target).quantize()
