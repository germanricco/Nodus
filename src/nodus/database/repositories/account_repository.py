"""Persistence of accounts."""

from __future__ import annotations

import dataclasses
import sqlite3

from nodus.database.repositories.base import Repository
from nodus.models.account import Account, AccountType
from nodus.models.currency import Currency
from nodus.models.money import Money

# Initial balance plus incomes minus expenses. Accounts without transactions get their
# initial balance thanks to the LEFT JOIN and COALESCE.
_BALANCES_SQL = """
    SELECT a.id,
           a.initial_balance_cents + COALESCE(SUM(
               CASE t.type WHEN 'income' THEN t.amount_cents ELSE -t.amount_cents END
           ), 0) AS balance_cents
    FROM accounts a
    LEFT JOIN transactions t ON t.account_id = a.id
    GROUP BY a.id
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

    def balances_cents(self) -> dict[int, int]:
        """Current balance of every account, in cents of the account's own currency."""
        return {row["id"]: row["balance_cents"] for row in self._fetch_all(_BALANCES_SQL)}

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
