"""Persistence of savings goals and of the share of each account that counts for them."""

from __future__ import annotations

import dataclasses
import sqlite3
from collections import defaultdict

from nodus.database.repositories.base import Repository, day_or_none, iso_or_none
from nodus.models.currency import Currency
from nodus.models.goal import Goal, GoalShare
from nodus.models.money import Money


class GoalRepository(Repository):
    """Reads and writes the ``goals`` table and the share of each account that counts for a goal;
    the rules live in ``GoalService``."""

    TABLE = "goals"

    def add(self, goal: Goal) -> Goal:
        goal_id = self._insert(
            "INSERT INTO goals (name, target_cents, currency, target_date, reached_on,"
            " reached_seen, is_archived, position) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            self._values(goal),
        )
        self._set_shares(goal_id, goal.shares)
        return dataclasses.replace(goal, id=goal_id)

    def update(self, goal: Goal) -> None:
        self._execute(
            "UPDATE goals SET name = ?, target_cents = ?, currency = ?, target_date = ?,"
            " reached_on = ?, reached_seen = ?, is_archived = ?, position = ? WHERE id = ?",
            (*self._values(goal), goal.id),
        )
        self._set_shares(goal.id, goal.shares)

    def get(self, goal_id: int) -> Goal | None:
        row = self._fetch_one("SELECT * FROM goals WHERE id = ?", (goal_id,))
        return self._from_row(row, self._shares().get(goal_id, ())) if row else None

    def list(self) -> list[Goal]:
        shares = self._shares()
        return [
            self._from_row(row, shares.get(row["id"], ()))
            for row in self._fetch_all("SELECT * FROM goals")
        ]

    def next_position(self) -> int:
        return self._next_position()

    def delete(self, goal_id: int) -> None:
        self._delete_id(goal_id)

    def _set_shares(self, goal_id: int, shares: tuple[GoalShare, ...]) -> None:
        self._execute("DELETE FROM goal_accounts WHERE goal_id = ?", (goal_id,))
        self._database.connection.executemany(
            "INSERT INTO goal_accounts (goal_id, account_id, share_percent) VALUES (?, ?, ?)",
            [(goal_id, share.account_id, share.percent) for share in shares],
        )

    def _shares(self) -> dict[int, tuple[GoalShare, ...]]:
        found: dict[int, list[GoalShare]] = defaultdict(list)
        rows = self._fetch_all(
            "SELECT goal_id, account_id, share_percent FROM goal_accounts ORDER BY rowid"
        )
        for row in rows:
            found[row["goal_id"]].append(GoalShare(row["account_id"], row["share_percent"]))
        return {goal_id: tuple(shares) for goal_id, shares in found.items()}

    @staticmethod
    def _values(goal: Goal) -> tuple:
        return (
            goal.name,
            goal.target.cents,
            goal.currency.value,
            iso_or_none(goal.target_date),
            iso_or_none(goal.reached_on),
            goal.reached_seen,
            goal.is_archived,
            goal.position,
        )

    @staticmethod
    def _from_row(row: sqlite3.Row, shares: tuple[GoalShare, ...]) -> Goal:
        currency = Currency(row["currency"])
        return Goal(
            id=row["id"],
            name=row["name"],
            target=Money(row["target_cents"], currency),
            target_date=day_or_none(row["target_date"]),
            shares=shares,
            reached_on=day_or_none(row["reached_on"]),
            reached_seen=bool(row["reached_seen"]),
            is_archived=bool(row["is_archived"]),
            position=row["position"],
        )
