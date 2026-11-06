"""User preferences and facts about where the data lives."""

from __future__ import annotations

from pathlib import Path

from nodus.config.paths import visible_path
from nodus.database.database import Database
from nodus.database.repositories.settings_repository import SettingsRepository
from nodus.models.currency import Currency


class SettingsService:
    """Reads and saves preferences stored in the user's own database file.

    Keeping them in the database means they travel with the data when the file is copied
    to another computer.
    """

    THEME_KEY = "theme"
    CHECK_UPDATES_KEY = "check_updates"
    RATE_SOURCE_KEY = "rate_source"
    LAST_ACCOUNT_KEY = "last_account_id"
    NET_WORTH_CURRENCY_KEY = "net_worth_currency"
    DISMISSED_VERSION_KEY = "dismissed_version"
    SIDEBAR_COLLAPSED_KEY = "sidebar_collapsed"

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
        return self._flag(self.CHECK_UPDATES_KEY, default=True)

    def set_check_updates(self, enabled: bool) -> None:
        self._set_flag(self.CHECK_UPDATES_KEY, enabled)

    def sidebar_collapsed(self) -> bool:
        """Whether the sidebar shows only its icons."""
        return self._flag(self.SIDEBAR_COLLAPSED_KEY, default=False)

    def set_sidebar_collapsed(self, collapsed: bool) -> None:
        self._set_flag(self.SIDEBAR_COLLAPSED_KEY, collapsed)

    def last_account_id(self) -> int | None:
        """The account of the last movement recorded, offered first in the next one."""
        value = self._settings.get(self.LAST_ACCOUNT_KEY)
        return int(value) if value and value.isdigit() else None

    def set_last_account_id(self, account_id: int) -> None:
        with self._database.transaction():
            self._settings.set(self.LAST_ACCOUNT_KEY, str(account_id))

    def net_worth_currency(self) -> Currency:
        """The currency the dashboard shows the net worth in; pesos until chosen."""
        value = self._settings.get(self.NET_WORTH_CURRENCY_KEY)
        return Currency(value) if value in {c.value for c in Currency} else Currency.ARS

    def set_net_worth_currency(self, currency: Currency) -> None:
        with self._database.transaction():
            self._settings.set(self.NET_WORTH_CURRENCY_KEY, currency.value)

    def dismissed_version(self) -> str | None:
        """The new version the user chose not to hear about again, if any."""
        return self._settings.get(self.DISMISSED_VERSION_KEY)

    def set_dismissed_version(self, version: str) -> None:
        with self._database.transaction():
            self._settings.set(self.DISMISSED_VERSION_KEY, version)

    def rate_source(self) -> str | None:
        """Where the dollar rate comes from ("manual", "bolsa"…), or None if never chosen."""
        return self._settings.get(self.RATE_SOURCE_KEY)

    def set_rate_source(self, source: str) -> None:
        with self._database.transaction():
            self._settings.set(self.RATE_SOURCE_KEY, source)

    def _flag(self, key: str, default: bool) -> bool:
        value = self._settings.get(key)
        return default if value is None else value != "false"

    def _set_flag(self, key: str, value: bool) -> None:
        with self._database.transaction():
            self._settings.set(key, "true" if value else "false")
