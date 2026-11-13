"""User preferences and facts about where the data lives."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from nodus.config.paths import visible_path
from nodus.config.system import windows_animations_on
from nodus.database.database import Database
from nodus.database.repositories.settings_repository import SettingsRepository
from nodus.models.currency import TOTAL_CURRENCIES, Currency


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
    LAST_SEEN_VERSION_KEY = "last_seen_version"
    SIDEBAR_COLLAPSED_KEY = "sidebar_collapsed"
    ACCOUNTS_FOLDED_KEY = "accounts_folded"
    AMOUNTS_HIDDEN_KEY = "amounts_hidden"
    REDUCE_MOTION_KEY = "reduce_motion"
    EXTERNAL_BACKUP_KEY = "last_external_backup"
    EXTERNAL_BACKUP_FOLDER_KEY = "external_backup_folder"
    BACKUP_REMINDER_KEY = "backup_reminder"
    BACKUP_REMINDER_DISMISSED_KEY = "backup_reminder_dismissed"

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

    def accounts_folded(self) -> bool:
        """Whether the sidebar keeps its list of accounts folded."""
        return self._flag(self.ACCOUNTS_FOLDED_KEY, default=False)

    def set_accounts_folded(self, folded: bool) -> None:
        self._set_flag(self.ACCOUNTS_FOLDED_KEY, folded)

    def amounts_hidden(self) -> bool:
        """Whether balances and the net worth show as "$ ••••", for privacy."""
        return self._flag(self.AMOUNTS_HIDDEN_KEY, default=False)

    def set_amounts_hidden(self, hidden: bool) -> None:
        self._set_flag(self.AMOUNTS_HIDDEN_KEY, hidden)

    def reduce_motion(self) -> bool:
        """Whether charts and figures jump to new data instead of moving to it. Until the
        user chooses, it follows Windows's «Show animations» setting."""
        return self._flag(self.REDUCE_MOTION_KEY, default=not windows_animations_on())

    def set_reduce_motion(self, reduced: bool) -> None:
        self._set_flag(self.REDUCE_MOTION_KEY, reduced)

    def last_external_backup(self) -> date | None:
        """The day of the last copy saved outside this computer, or None if never."""
        value = self._settings.get(self.EXTERNAL_BACKUP_KEY)
        return date.fromisoformat(value) if value else None

    def external_backup_folder(self) -> Path | None:
        """Where the last copy outside this computer went, offered again the next time."""
        value = self._settings.get(self.EXTERNAL_BACKUP_FOLDER_KEY)
        return Path(value) if value else None

    def set_external_backup(self, day: date, folder: Path) -> None:
        with self._database.transaction():
            self._settings.set(self.EXTERNAL_BACKUP_KEY, day.isoformat())
            self._settings.set(self.EXTERNAL_BACKUP_FOLDER_KEY, str(folder))

    def backup_reminder(self) -> bool:
        """Whether to remind, at the end of the month, to save a copy outside the PC."""
        return self._flag(self.BACKUP_REMINDER_KEY, default=True)

    def set_backup_reminder(self, enabled: bool) -> None:
        self._set_flag(self.BACKUP_REMINDER_KEY, enabled)

    def backup_reminder_dismissed(self) -> str | None:
        """The month ("2026-10") whose reminder the user put off with «Ahora no»."""
        return self._settings.get(self.BACKUP_REMINDER_DISMISSED_KEY)

    def set_backup_reminder_dismissed(self, month: str) -> None:
        with self._database.transaction():
            self._settings.set(self.BACKUP_REMINDER_DISMISSED_KEY, month)

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
        return next((c for c in TOTAL_CURRENCIES if c.value == value), Currency.ARS)

    def set_net_worth_currency(self, currency: Currency) -> None:
        with self._database.transaction():
            self._settings.set(self.NET_WORTH_CURRENCY_KEY, currency.value)

    def dismissed_version(self) -> str | None:
        """The new version the user chose not to hear about again, if any."""
        return self._settings.get(self.DISMISSED_VERSION_KEY)

    def set_dismissed_version(self, version: str) -> None:
        with self._database.transaction():
            self._settings.set(self.DISMISSED_VERSION_KEY, version)

    def last_seen_version(self) -> str | None:
        """The last version whose news the user saw, or None if never recorded."""
        return self._settings.get(self.LAST_SEEN_VERSION_KEY)

    def set_last_seen_version(self, version: str) -> None:
        with self._database.transaction():
            self._settings.set(self.LAST_SEEN_VERSION_KEY, version)

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
