"""User preferences and facts about where the data lives."""

from __future__ import annotations

from pathlib import Path

from nodus.database.database import Database
from nodus.database.repositories.settings_repository import SettingsRepository


class SettingsService:
    """Reads and saves preferences stored in the user's own database file.

    Keeping them in the database means they travel with the data when the file is copied
    to another computer.
    """

    THEME_KEY = "theme"

    def __init__(self, database: Database, settings: SettingsRepository) -> None:
        self._database = database
        self._settings = settings

    @property
    def data_file(self) -> Path:
        """The SQLite file that holds all of the user's data."""
        return self._database.path

    def theme_preference(self) -> str | None:
        """The saved theme ("light", "dark" or "system"), or None if never chosen."""
        return self._settings.get(self.THEME_KEY)

    def set_theme_preference(self, value: str) -> None:
        with self._database.transaction():
            self._settings.set(self.THEME_KEY, value)
