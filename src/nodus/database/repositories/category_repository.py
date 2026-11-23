"""Persistence of categories."""

from __future__ import annotations

import dataclasses
import sqlite3

from nodus.database.repositories.base import Repository
from nodus.models.category import Category, fixed_name
from nodus.models.transaction import TransactionType


class CategoryRepository(Repository):
    """Reads and writes the ``categories`` table; the rules live in ``CategoryService``."""

    TABLE = "categories"
    # What points to a category and moves with it when it is merged: (table, column).
    REFERENCES = (
        ("transactions", "category_id"),
        ("recurring_charges", "category_id"),
        ("payees", "default_category_id"),
    )

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
        return self._one_where("id", category_id)

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

    def get_refunds(self) -> Category:
        """The refunds category, marked by migration 012."""
        return self._from_row(self._fetch_one("SELECT * FROM categories WHERE is_refunds = 1"))

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

    def reassign_payee_defaults(self, from_category_id: int, to_category_id: int) -> None:
        """The payees whose default is one category take another instead."""
        self._execute(
            "UPDATE payees SET default_category_id = ? WHERE default_category_id = ?",
            (to_category_id, from_category_id),
        )

    def delete(self, category_id: int) -> None:
        self._delete_id(category_id)

    def row(self, category_id: int) -> dict | None:
        """The category as stored, for ``put_back`` (undoing a merge)."""
        return self._row(self.TABLE, category_id)

    def put_back(self, row: dict) -> None:
        self._put_back(self.TABLE, row)

    def references(self, category_id: int) -> dict[tuple[str, str], list[int]]:
        """The ids of the rows of each of ``REFERENCES`` that point to the category."""
        return {
            (table, column): [
                row["id"]
                for row in self._fetch_all(
                    f"SELECT id FROM {table} WHERE {column} = ?", (category_id,)
                )
            ]
            for table, column in self.REFERENCES
        }

    def point_to(self, references: dict[tuple[str, str], list[int]], category_id: int) -> None:
        """Makes the rows of ``references`` point to ``category_id`` again."""
        for (table, column), ids in references.items():
            self._database.connection.executemany(
                f"UPDATE {table} SET {column} = ? WHERE id = ?",
                [(category_id, row_id) for row_id in ids],
            )

    def budget_rows(self, category_id: int) -> list[dict]:
        """The category's monthly limits as stored: deleting it deletes them too."""
        rows = self._fetch_all("SELECT * FROM budget_limits WHERE category_id = ?", (category_id,))
        return [dict(row) for row in rows]

    def put_back_budget(self, row: dict) -> None:
        self._put_back("budget_limits", row)

    def move_budgets(self, from_category_id: int, to_category_id: int) -> None:
        """Gives one category's budget, with its history, to another."""
        self._execute(
            "UPDATE budget_limits SET category_id = ? WHERE category_id = ?",
            (to_category_id, from_category_id),
        )

    def delete_budget_rows(self, row_ids: list[int]) -> None:
        self._database.connection.executemany(
            "DELETE FROM budget_limits WHERE id = ?", [(row_id,) for row_id in row_ids]
        )

    def name_taken(self, kind: TransactionType, parent_id: int | None, name: str) -> bool:
        """Whether a category of ``kind`` under ``parent_id`` has ``name``, ignoring case,
        as the unique index of the table compares them."""
        row = self._fetch_one(
            "SELECT 1 FROM categories WHERE kind = ? AND COALESCE(parent_id, 0) = ?"
            " AND name = ? COLLATE NOCASE",
            (kind.value, parent_id or 0, name),
        )
        return row is not None

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Category:
        is_system, is_refunds = bool(row["is_system"]), bool(row["is_refunds"])
        return Category(
            id=row["id"],
            name=fixed_name(is_system, is_refunds) or row["name"],
            kind=TransactionType(row["kind"]),
            color=row["color"],
            parent_id=row["parent_id"],
            is_system=is_system,
            is_refunds=is_refunds,
        )
