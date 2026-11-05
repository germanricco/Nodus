"""Persistence of user preferences."""

from __future__ import annotations

from nodus.database.repositories.base import Repository


class SettingsRepository(Repository):
    """Key-value store for preferences, so new ones need no schema change."""

    def get(self, key: str) -> str | None:
        row = self._fetch_one("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else None

    def set(self, key: str, value: str) -> None:
        self._execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)"
            " ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
