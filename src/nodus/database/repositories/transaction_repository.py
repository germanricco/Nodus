"""Persistence of transactions."""

from __future__ import annotations

import dataclasses
import sqlite3
from datetime import date

from nodus.database.repositories.base import Repository
from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.payee import normalize_name
from nodus.models.transaction import Transaction, TransactionType
from nodus.models.transaction_filter import TransactionFilter

# The amount's currency is the account's, so every read joins accounts. The payee is
# joined so the text search can match its name.
_SELECT = (
    "SELECT t.*, a.currency FROM transactions t JOIN accounts a ON a.id = t.account_id"
    " LEFT JOIN payees p ON p.id = t.payee_id"
)


class TransactionRepository(Repository):
    def add(self, transaction: Transaction) -> Transaction:
        transaction_id = self._insert(
            "INSERT INTO transactions"
            " (account_id, type, amount_cents, occurred_on, category_id, note, transfer_id,"
            " payee_id, refund_of_id)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            self._values(transaction),
        )
        return dataclasses.replace(transaction, id=transaction_id)

    def update(self, transaction: Transaction) -> None:
        self._execute(
            "UPDATE transactions SET account_id = ?, type = ?, amount_cents = ?, occurred_on = ?,"
            " category_id = ?, note = ?, transfer_id = ?, payee_id = ?, refund_of_id = ?,"
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

    def date_range(self, criteria: TransactionFilter) -> tuple[date, date] | None:
        """The first and last day of the matching transactions, or None if there are none."""
        conditions, params = self._where(criteria)
        sql = _SELECT.replace("t.*, a.currency", "MIN(t.occurred_on), MAX(t.occurred_on)")
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        first, last = self._fetch_one(sql, params)
        if first is None:
            return None
        return date.fromisoformat(first), date.fromisoformat(last)

    def list_refunds_of(self, expense_id: int) -> list[Transaction]:
        """The refunds of ``expense_id``, newest first."""
        rows = self._fetch_all(
            f"{_SELECT} WHERE t.refund_of_id = ? ORDER BY t.occurred_on DESC, t.id DESC",
            (expense_id,),
        )
        return [self._from_row(row) for row in rows]

    def refund_totals(self) -> dict[int, list[Money]]:
        """What has been refunded of each refunded expense, one amount per currency."""
        rows = self._fetch_all(
            "SELECT t.refund_of_id, a.currency, SUM(t.amount_cents) AS cents"
            " FROM transactions t JOIN accounts a ON a.id = t.account_id"
            " WHERE t.refund_of_id IS NOT NULL GROUP BY t.refund_of_id, a.currency"
        )
        totals: dict[int, list[Money]] = {}
        for row in rows:
            money = Money(row["cents"], Currency(row["currency"]))
            totals.setdefault(row["refund_of_id"], []).append(money)
        return totals

    def unlink_refunds_of(self, expense_id: int) -> None:
        """Turns the refunds of ``expense_id`` back into plain income."""
        self._execute(
            "UPDATE transactions SET refund_of_id = NULL WHERE refund_of_id = ?", (expense_id,)
        )

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
        if criteria.payee_id is not None:
            conditions.append("t.payee_id = ?")
            params.append(criteria.payee_id)
        if criteria.tag_id is not None:
            conditions.append(
                "t.id IN (SELECT transaction_id FROM transaction_tags WHERE tag_id = ?)"
            )
            params.append(criteria.tag_id)
        if criteria.type is not None:
            conditions.append("t.type = ?")
            params.append(criteria.type.value)
        if criteria.is_transfer is not None:
            conditions.append(
                "t.transfer_id IS NOT NULL" if criteria.is_transfer else "t.transfer_id IS NULL"
            )
        if criteria.refund_linked is not None:
            linked = (
                "(t.refund_of_id IS NOT NULL"
                " OR EXISTS (SELECT 1 FROM transactions r WHERE r.refund_of_id = t.id))"
            )
            conditions.append(linked if criteria.refund_linked else f"NOT {linked}")
        if criteria.text:
            name_text = normalize_name(criteria.text)
            if name_text:
                conditions.append(
                    "(t.note LIKE ? OR p.normalized_name LIKE ? OR t.id IN ("
                    "SELECT tt.transaction_id FROM transaction_tags tt"
                    " JOIN tags g ON g.id = tt.tag_id WHERE g.normalized_name LIKE ?))"
                )
                params.extend([f"%{criteria.text}%"] + [f"%{name_text}%"] * 2)
            else:
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
            transaction.payee_id,
            transaction.refund_of_id,
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
            payee_id=row["payee_id"],
            refund_of_id=row["refund_of_id"],
        )
