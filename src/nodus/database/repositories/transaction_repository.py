"""Persistence of transactions."""

from __future__ import annotations

import dataclasses
import sqlite3
from dataclasses import dataclass
from datetime import date

from nodus.database.repositories.base import Repository
from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.transaction import Transaction, TransactionType

# The amount's currency is the account's, so every read joins accounts.
_SELECT = "SELECT t.*, a.currency FROM transactions t JOIN accounts a ON a.id = t.account_id"


@dataclass(frozen=True)
class TransactionFilter:
    """Criteria for listing transactions. Unset fields do not filter.

    ``category_id`` also matches the category's subcategories, and ``text`` searches the note.
    ``is_transfer`` keeps only transfer legs (True) or only income and expenses (False).
    Dates are inclusive.
    """

    start: date | None = None
    end: date | None = None
    account_id: int | None = None
    category_id: int | None = None
    type: TransactionType | None = None
    text: str | None = None
    is_transfer: bool | None = None
    limit: int | None = None


class TransactionRepository(Repository):
    def add(self, transaction: Transaction) -> Transaction:
        transaction_id = self._insert(
            "INSERT INTO transactions"
            " (account_id, type, amount_cents, occurred_on, category_id, note, transfer_id)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            self._values(transaction),
        )
        return dataclasses.replace(transaction, id=transaction_id)

    def update(self, transaction: Transaction) -> None:
        self._execute(
            "UPDATE transactions SET account_id = ?, type = ?, amount_cents = ?, occurred_on = ?,"
            " category_id = ?, note = ?, transfer_id = ?,"
            " updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now')"
            " WHERE id = ?",
            (*self._values(transaction), transaction.id),
        )

    def get(self, transaction_id: int) -> Transaction | None:
        row = self._fetch_one(f"{_SELECT} WHERE t.id = ?", (transaction_id,))
        return self._from_row(row) if row else None

    def list_transfer_legs(self, transfer_id: str) -> list[Transaction]:
        rows = self._fetch_all(f"{_SELECT} WHERE t.transfer_id = ?", (transfer_id,))
        return [self._from_row(row) for row in rows]

    def list(self, criteria: TransactionFilter) -> list[Transaction]:
        """Matching transactions, newest first."""
        conditions, params = self._where(criteria)
        sql = _SELECT
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY t.occurred_on DESC, t.id DESC"
        if criteria.limit is not None:
            sql += " LIMIT ?"
            params.append(criteria.limit)
        return [self._from_row(row) for row in self._fetch_all(sql, params)]

    def delete(self, transaction_id: int) -> None:
        self._execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))

    def delete_transfer(self, transfer_id: str) -> None:
        self._execute("DELETE FROM transactions WHERE transfer_id = ?", (transfer_id,))

    @staticmethod
    def _where(criteria: TransactionFilter) -> tuple[list[str], list]:
        conditions: list[str] = []
        params: list = []
        if criteria.start is not None:
            conditions.append("t.occurred_on >= ?")
            params.append(criteria.start.isoformat())
        if criteria.end is not None:
            conditions.append("t.occurred_on <= ?")
            params.append(criteria.end.isoformat())
        if criteria.account_id is not None:
            conditions.append("t.account_id = ?")
            params.append(criteria.account_id)
        if criteria.category_id is not None:
            conditions.append(
                "t.category_id IN (SELECT id FROM categories WHERE id = ? OR parent_id = ?)"
            )
            params.extend([criteria.category_id, criteria.category_id])
        if criteria.type is not None:
            conditions.append("t.type = ?")
            params.append(criteria.type.value)
        if criteria.is_transfer is not None:
            conditions.append(
                "t.transfer_id IS NOT NULL" if criteria.is_transfer else "t.transfer_id IS NULL"
            )
        if criteria.text:
            conditions.append("t.note LIKE ?")
            params.append(f"%{criteria.text}%")
        return conditions, params

    @staticmethod
    def _values(transaction: Transaction) -> tuple:
        return (
            transaction.account_id,
            transaction.type.value,
            transaction.amount.cents,
            transaction.occurred_on.isoformat(),
            transaction.category_id,
            transaction.note,
            transaction.transfer_id,
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Transaction:
        return Transaction(
            id=row["id"],
            account_id=row["account_id"],
            type=TransactionType(row["type"]),
            amount=Money(row["amount_cents"], Currency(row["currency"])),
            occurred_on=date.fromisoformat(row["occurred_on"]),
            category_id=row["category_id"],
            note=row["note"],
            transfer_id=row["transfer_id"],
        )
