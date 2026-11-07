"""Exchange rates of each foreign currency against the peso, and conversions with them."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from nodus.database.database import Database
from nodus.database.repositories.exchange_rate_repository import ExchangeRateRepository
from nodus.models.currency import HOME_CURRENCY, Currency
from nodus.models.exchange_rate import ExchangeRate
from nodus.models.money import Money
from nodus.services.errors import ValidationError


class ExchangeRateService:
    """Keeps, for each foreign currency, the history of how many pesos one unit is worth,
    and converts any amount with the rate of its day.

    The dollar rate is the one the user chooses (MEP, blue…), because the one that matters
    in Argentina is rarely the official one. Two foreign currencies convert through the
    peso: a euro in dollars is its pesos divided by a dollar's.
    """

    def __init__(self, database: Database, rates: ExchangeRateRepository) -> None:
        self._database = database
        self._rates = rates

    def set_rate(
        self, rate_date: date, pesos_per_unit: Decimal, currency: Currency = Currency.USD
    ) -> ExchangeRate:
        """Records how many pesos one unit of ``currency`` is worth on ``rate_date``,
        replacing that day's rate."""
        if not currency.is_foreign:
            raise ValueError("The peso has no exchange rate against itself")
        if pesos_per_unit <= 0:
            raise ValidationError("La cotización debe ser mayor que cero.")
        rate = ExchangeRate(None, rate_date, currency, HOME_CURRENCY, pesos_per_unit)
        with self._database.transaction():
            return self._rates.save(rate)

    def delete(self, rate_id: int) -> None:
        with self._database.transaction():
            self._rates.delete(rate_id)

    def history(self, currency: Currency = Currency.USD) -> list[ExchangeRate]:
        """The rates of ``currency``, newest first."""
        return self._rates.list(currency, HOME_CURRENCY)

    def rate_on(self, day: date, currency: Currency = Currency.USD) -> ExchangeRate | None:
        """The rate of ``currency`` in force on ``day``, or None if none was entered on or
        before it."""
        return self._rates.latest_on_or_before(day, currency, HOME_CURRENCY)

    def convert(self, money: Money, target: Currency, day: date) -> Money | None:
        """``money`` in ``target`` at the rates of ``day``; None when a rate is missing.

        Callers show "sin cotización" for None rather than an invented figure.
        """
        if money.currency is target:
            return money
        pesos = self._pesos_per_unit(money.currency, day)
        pesos_per_target = self._pesos_per_unit(target, day)
        if pesos is None or pesos_per_target is None:
            return None
        return Money.from_decimal(money.to_decimal() * pesos / pesos_per_target, target)

    def _pesos_per_unit(self, currency: Currency, day: date) -> Decimal | None:
        if not currency.is_foreign:
            return Decimal(1)
        rate = self.rate_on(day, currency)
        return rate.rate if rate else None
