"""Persistence of exchange rates."""

from __future__ import annotations

import dataclasses
import sqlite3
from datetime import date
from decimal import Decimal

from nodus.database.repositories.base import Repository
from nodus.models.currency import Currency
from nodus.models.exchange_rate import ExchangeRate


class ExchangeRateRepository(Repository):
    def save(self, rate: ExchangeRate) -> ExchangeRate:
        """Stores the rate, replacing any previous one for the same date and pair."""
        key = (rate.rate_date.isoformat(), rate.base.value, rate.quote.value)
        self._execute(
            "INSERT INTO exchange_rates (rate_date, base_currency, quote_currency, rate)"
            " VALUES (?, ?, ?, ?)"
            " ON CONFLICT (rate_date, base_currency, quote_currency)"
            " DO UPDATE SET rate = excluded.rate",
            (*key, str(rate.rate)),
        )
        # lastrowid is unreliable when the upsert updated an existing row, so read the id back.
        saved = self._fetch_one(
            "SELECT id FROM exchange_rates"
            " WHERE rate_date = ? AND base_currency = ? AND quote_currency = ?",
            key,
        )
        return dataclasses.replace(rate, id=saved["id"])

    def latest_on_or_before(
        self, day: date, base: Currency, quote: Currency
    ) -> ExchangeRate | None:
        """The rate in force on ``day``: the most recent one dated that day or earlier."""
        row = self._fetch_one(
            "SELECT * FROM exchange_rates"
            " WHERE base_currency = ? AND quote_currency = ? AND rate_date <= ?"
            " ORDER BY rate_date DESC LIMIT 1",
            (base.value, quote.value, day.isoformat()),
        )
        return self._from_row(row) if row else None

    def list(self, base: Currency, quote: Currency) -> list[ExchangeRate]:
        """History of a pair, newest first."""
        rows = self._fetch_all(
            "SELECT * FROM exchange_rates WHERE base_currency = ? AND quote_currency = ?"
            " ORDER BY rate_date DESC",
            (base.value, quote.value),
        )
        return [self._from_row(row) for row in rows]

    def delete(self, rate_id: int) -> None:
        self._execute("DELETE FROM exchange_rates WHERE id = ?", (rate_id,))

    @staticmethod
    def _from_row(row: sqlite3.Row) -> ExchangeRate:
        return ExchangeRate(
            id=row["id"],
            rate_date=date.fromisoformat(row["rate_date"]),
            base=Currency(row["base_currency"]),
            quote=Currency(row["quote_currency"]),
            rate=Decimal(row["rate"]),
        )
