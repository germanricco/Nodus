"""Persistence of account groups."""

from __future__ import annotations

import dataclasses
import sqlite3

from nodus.database.repositories.base import Repository
from nodus.models.account_group import AccountGroup


class AccountGroupRepository(Repository):
    TABLE = "account_groups"

    def add(self, group: AccountGroup) -> AccountGroup:
        group_id = self._insert(
            "INSERT INTO account_groups (name, normalized_name, position) VALUES (?, ?, ?)",
            (group.name, group.normalized_name, group.position),
        )
        return dataclasses.replace(group, id=group_id)

    def update(self, group: AccountGroup) -> None:
        self._execute(
            "UPDATE account_groups SET name = ?, normalized_name = ?, position = ? WHERE id = ?",
            (group.name, group.normalized_name, group.position, group.id),
        )

    def get(self, group_id: int) -> AccountGroup | None:
        return self._one_where("id", group_id)

    def find_by_normalized(self, normalized: str) -> AccountGroup | None:
        return self._one_where("normalized_name", normalized)

    def list(self) -> list[AccountGroup]:
        return [self._from_row(row) for row in self._fetch_all("SELECT * FROM account_groups")]

    def next_position(self) -> int:
        return self._next_position()

    def set_positions(self, positions: dict[int, int]) -> None:
        self._set_positions(positions)

    def delete(self, group_id: int) -> None:
        """Deletes the group; its accounts are left without one by the foreign key."""
        self._delete_id(group_id)

    @staticmethod
    def _from_row(row: sqlite3.Row) -> AccountGroup:
        return AccountGroup(id=row["id"], name=row["name"], position=row["position"])
