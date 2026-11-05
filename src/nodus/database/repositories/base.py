"""Shared behaviour for repositories."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from typing import Any

from nodus.database.database import Database


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
