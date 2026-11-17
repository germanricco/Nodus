"""Persistence of recurring charges."""

from __future__ import annotations

import dataclasses
import sqlite3
from datetime import date
from decimal import Decimal

from nodus.database.repositories.base import Repository
from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.recurring_charge import Frequency, RecurringCharge

_SELECT = "SELECT * FROM recurring_charges"


class RecurringChargeRepository(Repository):
    def add(self, charge: RecurringCharge) -> RecurringCharge:
        charge_id = self._insert(
            "INSERT INTO recurring_charges (name, amount_cents, account_id, category_id,"
            " frequency, anchor_day, next_due_on, is_active, note, currency, last_paid_rate)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            self._values(charge),
        )
        return dataclasses.replace(charge, id=charge_id)

    def update(self, charge: RecurringCharge) -> None:
        self._execute(
            "UPDATE recurring_charges SET name = ?, amount_cents = ?, account_id = ?,"
            " category_id = ?, frequency = ?, anchor_day = ?, next_due_on = ?, is_active = ?,"
            " note = ?, currency = ?, last_paid_rate = ? WHERE id = ?",
            (*self._values(charge), charge.id),
        )

    def get(self, charge_id: int) -> RecurringCharge | None:
        row = self._fetch_one(f"{_SELECT} WHERE id = ?", (charge_id,))
        return self._from_row(row) if row else None

    def list(self) -> list[RecurringCharge]:
        return [self._from_row(row) for row in self._fetch_all(f"{_SELECT} ORDER BY id")]

    def count_for_account(self, account_id: int) -> int:
        row = self._fetch_one(
            "SELECT COUNT(*) AS charges FROM recurring_charges WHERE account_id = ?",
            (account_id,),
        )
        return row["charges"]

    def delete(self, charge_id: int) -> None:
        self._execute("DELETE FROM recurring_charges WHERE id = ?", (charge_id,))

    @staticmethod
    def _values(charge: RecurringCharge) -> tuple:
        return (
            charge.name,
            charge.amount.cents,
            charge.account_id,
            charge.category_id,
            charge.frequency.value,
            charge.anchor_day,
            charge.next_due_on.isoformat(),
            charge.is_active,
            charge.note,
            charge.amount.currency.value,
            None if charge.last_paid_rate is None else str(charge.last_paid_rate),
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> RecurringCharge:
        return RecurringCharge(
            id=row["id"],
            name=row["name"],
            amount=Money(row["amount_cents"], Currency(row["currency"])),
            account_id=row["account_id"],
            category_id=row["category_id"],
            frequency=Frequency(row["frequency"]),
            anchor_day=row["anchor_day"],
            next_due_on=date.fromisoformat(row["next_due_on"]),
            is_active=bool(row["is_active"]),
            note=row["note"],
            last_paid_rate=(
                None if row["last_paid_rate"] is None else Decimal(row["last_paid_rate"])
            ),
        )
