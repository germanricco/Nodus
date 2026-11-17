"""Persistence of payees."""

from __future__ import annotations

import dataclasses
import sqlite3
from datetime import date

from nodus.database.repositories.base import Repository
from nodus.models.payee import Payee, PayeeUsage
from nodus.models.transaction import TransactionType


class PayeeRepository(Repository):
    TABLE = "payees"

    def add(self, payee: Payee) -> Payee:
        payee_id = self._insert(
            "INSERT INTO payees (name, normalized_name, default_category_id) VALUES (?, ?, ?)",
            (payee.name, payee.normalized_name, payee.default_category_id),
        )
        return dataclasses.replace(payee, id=payee_id)

    def update(self, payee: Payee) -> None:
        self._execute(
            "UPDATE payees SET name = ?, normalized_name = ?, default_category_id = ? WHERE id = ?",
            (payee.name, payee.normalized_name, payee.default_category_id, payee.id),
        )

    def get(self, payee_id: int) -> Payee | None:
        return self._one_where("id", payee_id)

    def find_by_normalized(self, normalized: str) -> Payee | None:
        return self._one_where("normalized_name", normalized)

    def list(self) -> list[Payee]:
        return [self._from_row(row) for row in self._fetch_all("SELECT * FROM payees")]

    def count_transactions(self, payee_id: int) -> int:
        row = self._fetch_one("SELECT COUNT(*) FROM transactions WHERE payee_id = ?", (payee_id,))
        return row[0]

    def usage(self, kind: TransactionType, since: date, until: date) -> dict[int, PayeeUsage]:
        """How each payee was used in ``kind`` transactions from ``since`` to ``until``,
        by payee id. Transfers have no payee; the installments of one purchase count once."""
        rows = self._fetch_all(
            """
            SELECT payee_id, category_id, MAX(occurred_on) AS last_used,
                   COUNT(DISTINCT COALESCE(installment_plan_id, -id)) AS uses
            FROM transactions
            WHERE payee_id IS NOT NULL AND transfer_id IS NULL AND type = ?
              AND occurred_on BETWEEN ? AND ?
            GROUP BY payee_id, category_id
            """,
            (kind.value, since.isoformat(), until.isoformat()),
        )
        usage: dict[int, PayeeUsage] = {}
        for row in rows:
            last_used = date.fromisoformat(row["last_used"])
            found = usage.get(row["payee_id"])
            by_category = dict(found.uses_by_category) if found else {}
            by_category[row["category_id"]] = row["uses"]
            usage[row["payee_id"]] = PayeeUsage(
                uses=(found.uses if found else 0) + row["uses"],
                last_used=max(last_used, found.last_used) if found else last_used,
                uses_by_category=by_category,
            )
        return usage

    def reassign(self, source_id: int, target_id: int) -> None:
        """Moves every transaction of ``source_id`` to ``target_id``."""
        self._execute(
            "UPDATE transactions SET payee_id = ? WHERE payee_id = ?", (target_id, source_id)
        )

    def delete(self, payee_id: int) -> None:
        self._delete_id(payee_id)

    def row(self, payee_id: int) -> dict | None:
        """The payee as stored, for ``put_back`` (undoing a merge)."""
        return self._row("payees", payee_id)

    def put_back(self, row: dict) -> None:
        self._put_back("payees", row)

    def transaction_ids(self, payee_id: int) -> list[int]:
        rows = self._fetch_all("SELECT id FROM transactions WHERE payee_id = ?", (payee_id,))
        return [row["id"] for row in rows]

    def assign(self, transaction_ids: list[int], payee_id: int | None) -> None:
        """Gives ``payee_id`` to the transactions ``transaction_ids``."""
        self._database.connection.executemany(
            "UPDATE transactions SET payee_id = ? WHERE id = ?",
            [(payee_id, transaction_id) for transaction_id in transaction_ids],
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Payee:
        return Payee(id=row["id"], name=row["name"], default_category_id=row["default_category_id"])
