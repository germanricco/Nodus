"""Persistence of categories."""

from __future__ import annotations

import dataclasses
import sqlite3

from nodus.database.repositories.base import Repository
from nodus.models.category import Category
from nodus.models.transaction import TransactionType


class CategoryRepository(Repository):
    def add(self, category: Category) -> Category:
        category_id = self._insert(
            "INSERT INTO categories (name, kind, color, parent_id, is_system)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                category.name,
                category.kind.value,
                category.color,
                category.parent_id,
                category.is_system,
            ),
        )
        return dataclasses.replace(category, id=category_id)

    def update(self, category: Category) -> None:
        self._execute(
            "UPDATE categories SET name = ?, color = ? WHERE id = ?",
            (category.name, category.color, category.id),
        )

    def get(self, category_id: int) -> Category | None:
        row = self._fetch_one("SELECT * FROM categories WHERE id = ?", (category_id,))
        return self._from_row(row) if row else None

    def list(self, kind: TransactionType | None = None) -> list[Category]:
        sql = "SELECT * FROM categories"
        params: tuple = ()
        if kind is not None:
            sql += " WHERE kind = ?"
            params = (kind.value,)
        rows = self._fetch_all(sql, params)
        return [self._from_row(row) for row in rows]

    def get_system(self, kind: TransactionType) -> Category:
        """The "Otros" category of ``kind``, created by the initial migration."""
        row = self._fetch_one(
            "SELECT * FROM categories WHERE kind = ? AND is_system = 1", (kind.value,)
        )
        return self._from_row(row)

    def subcategory_ids(self, parent_id: int) -> list[int]:
        rows = self._fetch_all("SELECT id FROM categories WHERE parent_id = ?", (parent_id,))
        return [row["id"] for row in rows]

    def count_transactions(self, category_ids: list[int]) -> int:
        placeholders = ", ".join("?" * len(category_ids))
        row = self._fetch_one(
            f"SELECT COUNT(*) AS total FROM transactions WHERE category_id IN ({placeholders})",
            category_ids,
        )
        return row["total"]

    def reassign_transactions(self, from_category_id: int, to_category_id: int) -> None:
        """Moves the category's transactions and recurring charges to another category."""
        for table in ("transactions", "recurring_charges"):
            self._execute(
                f"UPDATE {table} SET category_id = ? WHERE category_id = ?",
                (to_category_id, from_category_id),
            )

    def delete(self, category_id: int) -> None:
        self._execute("DELETE FROM categories WHERE id = ?", (category_id,))

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Category:
        return Category(
            id=row["id"],
            name=row["name"],
            kind=TransactionType(row["kind"]),
            color=row["color"],
            parent_id=row["parent_id"],
            is_system=bool(row["is_system"]),
        )
