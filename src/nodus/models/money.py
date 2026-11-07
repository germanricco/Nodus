"""Exact monetary amounts.

Amounts are kept as an integer number of cents, because floats accumulate rounding errors
that are unacceptable in financial balances. A currency without cents (the Chilean peso)
still counts in hundredths, always whole units, so every amount is stored the same way.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

from nodus.models.currency import Currency

CENTS_PER_UNIT = 100
_CENT = Decimal("0.01")
_UNIT = Decimal("1")


class CurrencyMismatchError(ValueError):
    """Raised when operating on amounts of different currencies without converting first."""


@dataclass(frozen=True, slots=True)
class Money:
    """An immutable amount of money in a single currency."""

    cents: int
    currency: Currency

    def __post_init__(self) -> None:
        # bool is a subclass of int, but True cents is always a bug.
        if not isinstance(self.cents, int) or isinstance(self.cents, bool):
            raise TypeError(f"Money cents must be an int, got {type(self.cents).__name__}")

    @classmethod
    def zero(cls, currency: Currency) -> Money:
        return cls(0, currency)

    @classmethod
    def from_decimal(cls, value: Decimal | str | int, currency: Currency) -> Money:
        """Builds an amount from units (e.g. "1234.56"), rounding half to even to the
        currency's smallest unit: the cent, or the whole unit for the Chilean peso.

        Floats are rejected: by the time a value is a float, precision may already be lost.
        """
        if isinstance(value, float):
            raise TypeError("Use Decimal or str for money, never float")
        step = _CENT if currency.decimals else _UNIT
        units = Decimal(value).quantize(step, rounding=ROUND_HALF_EVEN)
        return cls(int(units * CENTS_PER_UNIT), currency)

    def to_decimal(self) -> Decimal:
        return Decimal(self.cents) / CENTS_PER_UNIT

    @property
    def is_zero(self) -> bool:
        return self.cents == 0

    @property
    def is_negative(self) -> bool:
        return self.cents < 0

    def __add__(self, other: Money) -> Money:
        self._require_same_currency(other)
        return Money(self.cents + other.cents, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._require_same_currency(other)
        return Money(self.cents - other.cents, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.cents, self.currency)

    def __lt__(self, other: Money) -> bool:
        self._require_same_currency(other)
        return self.cents < other.cents

    def format(self) -> str:
        """Formats in Argentine style: "$ 1.234,56", "-US$ 10,00"."""
        return f"{self._sign}{self.currency.symbol} {self._unsigned_number()}"

    def format_number(self) -> str:
        """The number alone, without symbol: "1.234,56", "-10,00"."""
        return f"{self._sign}{self._unsigned_number()}"

    def format_plain(self) -> str:
        """The number without thousands separators: "-1234,56". Spreadsheets in Spanish read
        it as a number, while "1.234,56" may be taken as text."""
        units, cents = divmod(abs(self.cents), CENTS_PER_UNIT)
        return f"{self._sign}{units}{self._decimal_part(cents)}"

    @property
    def _sign(self) -> str:
        return "-" if self.is_negative else ""

    def _unsigned_number(self) -> str:
        units, cents = divmod(abs(self.cents), CENTS_PER_UNIT)
        grouped_units = f"{units:,}".replace(",", ".")
        return f"{grouped_units}{self._decimal_part(cents)}"

    def _decimal_part(self, cents: int) -> str:
        """ ",56", or nothing for a currency without cents."""
        return f",{cents:02d}" if self.currency.decimals else ""

    def __str__(self) -> str:
        return self.format()

    def _require_same_currency(self, other: Money) -> None:
        if self.currency is not other.currency:
            raise CurrencyMismatchError(
                f"Cannot combine {self.currency.value} and {other.currency.value}"
                " without converting"
            )
