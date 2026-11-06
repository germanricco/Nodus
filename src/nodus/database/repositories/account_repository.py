"""Persistence of accounts."""

from __future__ import annotations

import dataclasses
import sqlite3
from datetime import date

from nodus.database.repositories.base import Repository
from nodus.models.account import Account, AccountType
from nodus.models.currency import Currency
from nodus.models.money import Money

# Initial balance plus incomes minus expenses plus value adjustments, up to a day when
# one is given. COALESCE gives an account without any of them its initial balance.
_BALANCES_SQL = """
    SELECT a.id,
           a.initial_balance_cents
           + COALESCE((
               SELECT SUM(CASE t.type WHEN 'income' THEN t.amount_cents ELSE -t.amount_cents END)
               FROM transactions t
               WHERE t.account_id = a.id AND (:day IS NULL OR t.occurred_on <= :day)
           ), 0)
           + COALESCE((
               SELECT SUM(v.amount_cents)
               FROM value_adjustments v
               WHERE v.account_id = a.id AND (:day IS NULL OR v.occurred_on <= :day)
           ), 0) AS balance_cents
    FROM accounts a
"""


class AccountRepository(Repository):
    def add(self, account: Account) -> Account:
        account_id = self._insert(
            "INSERT INTO accounts (name, type, currency, initial_balance_cents, is_archived)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                account.name,
                account.type.value,
                account.currency.value,
                account.initial_balance.cents,
                account.is_archived,
            ),
        )
        return dataclasses.replace(account, id=account_id)

    def update(self, account: Account) -> None:
        self._execute(
            "UPDATE accounts SET name = ?, type = ?, currency = ?, initial_balance_cents = ?,"
            " is_archived = ? WHERE id = ?",
            (
                account.name,
                account.type.value,
                account.currency.value,
                account.initial_balance.cents,
                account.is_archived,
                account.id,
            ),
        )

    def get(self, account_id: int) -> Account | None:
        row = self._fetch_one("SELECT * FROM accounts WHERE id = ?", (account_id,))
        return self._from_row(row) if row else None

    def list(self, include_archived: bool = False) -> list[Account]:
        sql = "SELECT * FROM accounts"
        if not include_archived:
            sql += " WHERE is_archived = 0"
        rows = self._fetch_all(sql)
        return [self._from_row(row) for row in rows]

    def count_transactions(self, account_id: int) -> tuple[int, int]:
        """(movements, transfers) recorded in the account; a transfer counts in both."""
        row = self._fetch_one(
            "SELECT COUNT(*) AS movements, COUNT(transfer_id) AS transfers"
            " FROM transactions WHERE account_id = ?",
            (account_id,),
        )
        return row["movements"], row["transfers"]

    def delete(self, account_id: int) -> None:
        """Deletes the account with all its movements. Transfers go whole, other leg
        included, so no account is left with half a transfer."""
        self._execute(
            "DELETE FROM transactions WHERE transfer_id IN"
            " (SELECT transfer_id FROM transactions WHERE account_id = ?)",
            (account_id,),
        )
        self._execute("DELETE FROM transactions WHERE account_id = ?", (account_id,))
        self._execute("DELETE FROM accounts WHERE id = ?", (account_id,))

    def balances_cents(self, on: date | None = None) -> dict[int, int]:
        """Balance of every account at the end of ``on`` (today's if None), in cents of the
        account's own currency."""
        day = on.isoformat() if on else None
        rows = self._execute(_BALANCES_SQL, {"day": day}).fetchall()
        return {row["id"]: row["balance_cents"] for row in rows}

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Account:
        currency = Currency(row["currency"])
        return Account(
            id=row["id"],
            name=row["name"],
            type=AccountType(row["type"]),
            currency=currency,
            initial_balance=Money(row["initial_balance_cents"], currency),
            is_archived=bool(row["is_archived"]),
        )
