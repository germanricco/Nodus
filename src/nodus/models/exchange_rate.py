"""Exchange rates between currencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from nodus.models.currency import Currency
from nodus.models.money import Money


@dataclass(frozen=True)
class ImpliedRate:
    """What one unit of ``base`` cost in ``quote`` in an exchange: "US$ 1 = $ 1.215,50"."""

    base: Currency
    quote: Currency
    value: Decimal


def implied_rate(first: Money, second: Money) -> ImpliedRate | None:
    """The rate implied by exchanging one amount for the other, in either order.

    For a transfer from pesos to dollars this is the rate actually obtained. It is given per
    unit of the currency worth more (the smaller amount), as people quote rates: per dollar
    against pesos, per euro against dollars. None when both amounts are in the same
    currency or either is zero.
    """
    if first.currency is second.currency or first.is_zero or second.is_zero:
        return None
    base, quote = sorted((first, second), key=lambda money: abs(money.to_decimal()))
    return ImpliedRate(
        base.currency, quote.currency, abs(quote.to_decimal()) / abs(base.to_decimal())
    )


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
