"""Exchange rates between currencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from nodus.models.currency import Currency
from nodus.models.money import Money


def implied_ars_per_usd(first: Money, second: Money) -> Decimal | None:
    """Pesos per dollar implied by exchanging one amount for the other, in either order.

    For a transfer from pesos to dollars this is the rate actually obtained. None when the
    amounts are not one in ARS and one in USD, or the dollar amount is zero.
    """
    amounts = {first.currency: first, second.currency: second}
    pesos, dollars = amounts.get(Currency.ARS), amounts.get(Currency.USD)
    if pesos is None or dollars is None or dollars.is_zero:
        return None
    return pesos.to_decimal() / dollars.to_decimal()


@dataclass(frozen=True)
class ExchangeRate:
    """Price of one unit of ``base`` in ``quote`` on a given date (e.g. 1 USD = 1200 ARS)."""

    id: int | None
    rate_date: date
    base: Currency
    quote: Currency
    rate: Decimal

    def __post_init__(self) -> None:
        if self.base is self.quote:
            raise ValueError("An exchange rate needs two different currencies")
        if self.rate <= 0:
            raise ValueError("Exchange rate must be positive")

    def convert(self, money: Money) -> Money:
        """Converts between ``base`` and ``quote`` in either direction, rounding to the cent."""
        if money.currency is self.base:
            return Money.from_decimal(money.to_decimal() * self.rate, self.quote)
        if money.currency is self.quote:
            return Money.from_decimal(money.to_decimal() / self.rate, self.base)
        raise ValueError(f"This rate does not convert {money.currency.value}")
