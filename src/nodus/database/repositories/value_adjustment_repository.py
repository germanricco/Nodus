"""Persistence of value adjustments."""

from __future__ import annotations

import dataclasses
import sqlite3
from datetime import date

from nodus.database.repositories.base import Repository
from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.value_adjustment import ValueAdjustment


class ValueAdjustmentRepository(Repository):
    def add(self, adjustment: ValueAdjustment) -> ValueAdjustment:
        adjustment_id = self._insert(
            "INSERT INTO value_adjustments (account_id, occurred_on, amount_cents, note)"
            " VALUES (?, ?, ?, ?)",
            (
                adjustment.account_id,
                adjustment.occurred_on.isoformat(),
                adjustment.amount.cents,
                adjustment.note,
            ),
        )
        return dataclasses.replace(adjustment, id=adjustment_id)

    def get(self, adjustment_id: int) -> ValueAdjustment | None:
        row = self._fetch_one(_SELECT + " WHERE v.id = ?", (adjustment_id,))
        return self._from_row(row) if row else None

    def delete(self, adjustment_id: int) -> None:
        self._execute("DELETE FROM value_adjustments WHERE id = ?", (adjustment_id,))

    def list(
        self, account_id: int | None = None, start: date | None = None, end: date | None = None
    ) -> list[ValueAdjustment]:
        """Adjustments, oldest first, of one account or all, within the days given."""
        conditions, params = [], []
        if account_id is not None:
            conditions.append("v.account_id = ?")
            params.append(account_id)
        if start is not None:
            conditions.append("v.occurred_on >= ?")
            params.append(start.isoformat())
        if end is not None:
            conditions.append("v.occurred_on <= ?")
            params.append(end.isoformat())
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self._fetch_all(_SELECT + where + " ORDER BY v.occurred_on, v.id", params)
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row) -> ValueAdjustment:
        return ValueAdjustment(
            id=row["id"],
            account_id=row["account_id"],
            occurred_on=date.fromisoformat(row["occurred_on"]),
            amount=Money(row["amount_cents"], Currency(row["currency"])),
            note=row["note"],
        )


# The currency is the account's, like a transaction's.
_SELECT = "SELECT v.*, a.currency FROM value_adjustments v JOIN accounts a ON a.id = v.account_id"
