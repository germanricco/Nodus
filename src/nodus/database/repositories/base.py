"""Shared behaviour for repositories."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import date
from typing import Any

from nodus.database.database import Database

# Values per ``IN`` list: well below the 999 parameters older SQLite versions allow.
_IN_CHUNK = 500

# ``LIKE`` with a backslash as escape character, for ``contains`` patterns.
LIKE = "LIKE ? ESCAPE '\\'"


def iso_or_none(day: date | None) -> str | None:
    """How an optional date is stored: ISO text, or NULL."""
    return day.isoformat() if day else None


def day_or_none(text: str | None) -> date | None:
    """An optional date as stored, read back."""
    return date.fromisoformat(text) if text else None


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

    # The table a subclass keeps its records in, for the helpers below.
    TABLE = ""

    def __init__(self, database: Database) -> None:
        self._database = database

    def _one_where(self, column: str, value: Any) -> Any:
        """The record whose ``column`` is ``value``, built by ``_from_row``, or None."""
        row = self._fetch_one(f"SELECT * FROM {self.TABLE} WHERE {column} = ?", (value,))
        return self._from_row(row) if row else None

    def _delete_id(self, row_id: int) -> None:
        self._execute(f"DELETE FROM {self.TABLE} WHERE id = ?", (row_id,))

    def _next_position(self) -> int:
        """The position after the last record, so a new one goes at the end."""
        row = self._fetch_one(f"SELECT COALESCE(MAX(position), -1) + 1 AS next FROM {self.TABLE}")
        return row["next"]

    def _set_positions(self, positions: dict[int, int]) -> None:
        """Saves the position of each record id in ``positions``."""
        self._database.connection.executemany(
            f"UPDATE {self.TABLE} SET position = ? WHERE id = ?",
            [(position, row_id) for row_id, position in positions.items()],
        )

    def _execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        return self._database.connection.execute(sql, params)

    def _fetch_one(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        return self._execute(sql, params).fetchone()

    def _fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        return self._execute(sql, params).fetchall()

    def _fetch_in(self, sql: str, values: Sequence[Any]) -> list[sqlite3.Row]:
        """The rows of ``sql``, whose ``{}`` is filled with an ``IN`` list of ``values``,
        a chunk at a time so no list goes over SQLite's limit of parameters."""
        rows: list[sqlite3.Row] = []
        for start in range(0, len(values), _IN_CHUNK):
            chunk = values[start : start + _IN_CHUNK]
            rows += self._fetch_all(sql.format(", ".join("?" * len(chunk))), chunk)
        return rows

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
