"""User preferences and facts about where the data lives."""

from __future__ import annotations

from pathlib import Path

from nodus.config.paths import visible_path
from nodus.database.database import Database
from nodus.database.repositories.settings_repository import SettingsRepository


class SettingsService:
    """Reads and saves preferences stored in the user's own database file.

    Keeping them in the database means they travel with the data when the file is copied
    to another computer.
    """

    THEME_KEY = "theme"
    CHECK_UPDATES_KEY = "check_updates"
    RATE_SOURCE_KEY = "rate_source"
    LAST_ACCOUNT_KEY = "last_account_id"

    def __init__(self, database: Database, settings: SettingsRepository) -> None:
        self._database = database
        self._settings = settings

    @property
    def data_file(self) -> Path:
        """The SQLite file that holds all of the user's data, where the user can find it."""
        return visible_path(self._database.path)

    def theme_preference(self) -> str | None:
        """The saved theme ("light", "dark" or "system"), or None if never chosen."""
        return self._settings.get(self.THEME_KEY)

    def set_theme_preference(self, value: str) -> None:
        with self._database.transaction():
            self._settings.set(self.THEME_KEY, value)

    def check_updates(self) -> bool:
        """Whether to look for a new version on startup; on unless the user turned it off."""
        return self._settings.get(self.CHECK_UPDATES_KEY) != "false"

    def set_check_updates(self, enabled: bool) -> None:
        with self._database.transaction():
            self._settings.set(self.CHECK_UPDATES_KEY, "true" if enabled else "false")

    def rate_source(self) -> str | None:
        """Where the dollar rate comes from ("manual", "bolsa"…), or None if never chosen."""
        return self._settings.get(self.RATE_SOURCE_KEY)

    def set_rate_source(self, source: str) -> None:
        with self._database.transaction():
            self._settings.set(self.RATE_SOURCE_KEY, source)
