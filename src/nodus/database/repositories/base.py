"""Shared behaviour for repositories."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from typing import Any

from nodus.database.database import Database

# ``LIKE`` with a backslash as escape character, for ``contains`` patterns.
LIKE = "LIKE ? ESCAPE '\\'"


def contains(text: str) -> str:
    """The ``LIKE`` pattern that finds ``text`` anywhere, read literally: without
    escaping, a «%» typed in the search would match everything and «_» any character."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class Repository:
    """Base class for the objects that translate between table rows and domain models.

    Repositories only read and write; they never commit. The calling service decides the
    transaction boundaries with ``Database.transaction()``.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    def _execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        return self._database.connection.execute(sql, params)

    def _fetch_one(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        return self._execute(sql, params).fetchone()

    def _fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        return self._execute(sql, params).fetchall()

    def _insert(self, sql: str, params: Sequence[Any] = ()) -> int:
        """Runs an INSERT and returns the id of the new row."""
        return self._execute(sql, params).lastrowid

    def _row(self, table: str, row_id: int) -> dict[str, Any] | None:
        """Every column of one row, as it is stored, so it can be put back whole."""
        row = self._fetch_one(f"SELECT * FROM {table} WHERE id = ?", (row_id,))
        return dict(row) if row else None

    def _put_back(self, table: str, row: dict[str, Any]) -> None:
        """Inserts ``row`` again with its own id and creation time: undoing a delete."""
        columns = ", ".join(row)
        marks = ", ".join("?" * len(row))
        self._execute(f"INSERT INTO {table} ({columns}) VALUES ({marks})", tuple(row.values()))
