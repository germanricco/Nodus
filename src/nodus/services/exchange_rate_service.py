"""Exchange rate between dollars and pesos, entered by hand."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from nodus.database.database import Database
from nodus.database.repositories.exchange_rate_repository import ExchangeRateRepository
from nodus.models.currency import Currency
from nodus.models.exchange_rate import ExchangeRate
from nodus.models.money import Money
from nodus.services.errors import ValidationError


class ExchangeRateService:
    """Keeps the history of the USD→ARS rate the user chooses (MEP, blue…) and converts with it.

    The user types the rate because the one that matters in Argentina is rarely the
    official one; an automatic source can be added later behind this same interface.
    """

    BASE = Currency.USD
    QUOTE = Currency.ARS

    def __init__(self, database: Database, rates: ExchangeRateRepository) -> None:
        self._database = database
        self._rates = rates

    def set_rate(self, rate_date: date, ars_per_usd: Decimal) -> ExchangeRate:
        """Records how many pesos a dollar is worth on ``rate_date``, replacing that day's rate."""
        if ars_per_usd <= 0:
            raise ValidationError("La cotización debe ser mayor que cero.")
        rate = ExchangeRate(None, rate_date, self.BASE, self.QUOTE, ars_per_usd)
        with self._database.transaction():
            return self._rates.save(rate)

    def delete(self, rate_id: int) -> None:
        with self._database.transaction():
            self._rates.delete(rate_id)

    def history(self) -> list[ExchangeRate]:
        return self._rates.list(self.BASE, self.QUOTE)

    def rate_on(self, day: date) -> ExchangeRate | None:
        """The rate in force on ``day``, or None if none was entered on or before it."""
        return self._rates.latest_on_or_before(day, self.BASE, self.QUOTE)

    def convert(self, money: Money, target: Currency, day: date) -> Money | None:
        """``money`` in ``target`` at the rate of ``day``; None when there is no rate yet.

        Callers show "sin cotización" for None rather than an invented figure.
        """
        if money.currency is target:
            return money
        rate = self.rate_on(day)
        return rate.convert(money) if rate else None
