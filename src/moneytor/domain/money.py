"""``Money`` — a currency-tagged, ``Decimal``-backed value object.

All monetary values in MoneyTor flow through this type. It never uses ``float``
(rejecting it at construction), keeps currencies separated (raising on mixed
arithmetic), and rounds with banker's rounding (``ROUND_HALF_EVEN``).

Cross-currency conversion is intentionally *not* a ``Money`` operation — it
requires an FX rate and lives in :mod:`moneytor.fx`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Self

from .enums import Currency
from .errors import CurrencyMismatchError

# Accepted at construction; normalized to Decimal. float is deliberately absent.
type Numeric = Decimal | int | str
type Scalar = Decimal | int


def _to_decimal(value: Numeric) -> Decimal:
    """Normalize an accepted numeric input to ``Decimal``, rejecting ``float``.

    ``bool`` is rejected too (it is an ``int`` subclass and almost always a bug
    in a monetary context).
    """
    if isinstance(value, bool):
        raise TypeError("Money does not accept bool amounts.")
    if isinstance(value, float):
        raise TypeError(
            "Money rejects float amounts to avoid precision loss; "
            "pass a Decimal, int, or str (e.g. Money.of('19.99', Currency.CAD))."
        )
    if not isinstance(value, Decimal | int | str):
        raise TypeError(f"Unsupported amount type for Money: {type(value).__name__}.")
    return Decimal(str(value))


@dataclass(frozen=True, order=False)
class Money:
    """An immutable monetary amount in a single currency."""

    amount: Decimal = field()
    currency: Currency = field()

    def __post_init__(self) -> None:
        # Normalize whatever was passed (Decimal/int/str) and reject float/bool.
        object.__setattr__(self, "amount", _to_decimal(self.amount))
        if not isinstance(self.currency, Currency):
            raise TypeError("Money.currency must be a Currency.")

    # -- constructors ------------------------------------------------------- #

    @classmethod
    def of(cls, amount: Numeric, currency: Currency) -> Self:
        """Ergonomic constructor accepting ``Decimal``/``int``/``str``."""
        return cls(_to_decimal(amount), currency)

    @classmethod
    def zero(cls, currency: Currency) -> Self:
        """A zero amount in ``currency``."""
        return cls(Decimal("0"), currency)

    # -- guards ------------------------------------------------------------- #

    def _check_same_currency(self, other: Money) -> None:
        if self.currency is not other.currency:
            raise CurrencyMismatchError(
                f"Cannot operate on {self.currency.value} and "
                f"{other.currency.value}; convert via moneytor.fx first."
            )

    # -- arithmetic --------------------------------------------------------- #

    def __add__(self, other: Money) -> Money:
        self._check_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._check_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, factor: Scalar) -> Money:
        if isinstance(factor, bool | float):
            raise TypeError("Money can only be scaled by a Decimal or int.")
        return Money(self.amount * Decimal(str(factor)), self.currency)

    __rmul__ = __mul__

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)

    # -- comparisons (same-currency only) ----------------------------------- #

    def __lt__(self, other: Money) -> bool:
        self._check_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        self._check_same_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: Money) -> bool:
        self._check_same_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: Money) -> bool:
        self._check_same_currency(other)
        return self.amount >= other.amount

    # -- rounding & formatting --------------------------------------------- #

    def quantize(self, places: int = 2) -> Money:
        """Round to ``places`` decimals using banker's rounding."""
        exp = Decimal(1).scaleb(-places)
        return Money(self.amount.quantize(exp, rounding=ROUND_HALF_EVEN), self.currency)

    def format(self, places: int = 2) -> str:
        """Human-readable form, e.g. ``$1,234.56 CAD`` / ``-$50.00 USD``."""
        rounded = self.quantize(places).amount
        sign = "-" if rounded < 0 else ""
        return f"{sign}${abs(rounded):,.{places}f} {self.currency.value}"

    def __str__(self) -> str:
        return self.format()
