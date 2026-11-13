"""Daily copies of the user's database, copies saved outside the computer, and restoring
from one of them."""

from __future__ import annotations

import calendar
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from nodus.database.database import Database, DatabaseError, latest_schema_version
from nodus.services.errors import BackupError, ValidationError
from nodus.services.settings_service import SettingsService

_DAILY_NAME = re.compile(r"^nodus-(\d{4}-\d{2}-\d{2})\.db$")
# The reminder to save a copy outside the computer opens on the last days of each month.
REMINDER_DAYS = 3


def reminder_start(today: date) -> date:
    """The first day of the latest end-of-month reminder up to ``today``: the 28th of a
    30-day month, or of the month before while this one has not reached its end yet."""
    month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    start = month_end - timedelta(days=REMINDER_DAYS - 1)
    if today >= start:
        return start
    return today.replace(day=1) - timedelta(days=REMINDER_DAYS)


class BackupService:
    """Keeps one copy of the data per day in ``backups_dir``, up to ``KEEP`` of them.

    The data lives in a single file the user may never think about backing up; a copy a
    day costs a few KB and turns a mistake (or a damaged file) into a short trip back.

    Those copies share the computer's disk, so losing the computer loses them too. Once a
    month, Nodus reminds the user to save one outside it: a pen drive, an external disk or
    a folder that syncs to Drive or OneDrive.
    """

    KEEP = 10

    def __init__(self, database: Database, backups_dir: Path, settings: SettingsService) -> None:
        self._database = database
        self.backups_dir = backups_dir
        self._settings = settings
        self.last_error: str | None = None

    def create(self, today: date) -> Path:
        """Copies the data to today's backup, replacing an earlier one from today.

        Raises ``BackupError`` if the copy cannot be written.
        """
        destination = self.backups_dir / f"nodus-{today.isoformat()}.db"
        try:
            self._copy_to(destination)
            self._prune()
        except (OSError, sqlite3.Error) as error:
            raise BackupError(str(error)) from error
        return destination

    def create_if_due(self, today: date) -> Path | None:
        """Makes today's backup unless there already is one; runs every time Nodus opens.

        A failure is remembered in ``last_error`` instead of raised: a missing backup must
        not stop the user from opening their data.
        """
        if self.last_backup() == today:
            return None
        try:
            backup = self.create(today)
        except BackupError as error:
            self.last_error = f"No se pudo hacer la copia del día: {error}"
            return None
        self.last_error = None
        return backup

    def last_backup(self) -> date | None:
        days = self._daily_backups()
        return days[-1][0] if days else None

    def export_to(self, folder: Path, today: date) -> Path:
        """Saves a copy of the data in ``folder``, outside the computer, and remembers the
        day and the folder, which is offered again the next time.

        Raises ``BackupError`` if the copy cannot be written (a pen drive taken out).
        """
        destination = folder / f"nodus-{today.isoformat()}.db"
        try:
            self._database.backup_to(destination)
        except (OSError, sqlite3.Error) as error:
            raise BackupError(str(error)) from error
        self._settings.set_external_backup(today, folder)
        return destination

    def last_external_backup(self) -> date | None:
        return self._settings.last_external_backup()

    def external_folder(self) -> Path | None:
        """The folder of the last copy outside the computer, if it is there now: a pen
        drive that is plugged in."""
        folder = self._settings.external_backup_folder()
        return folder if folder is not None and folder.is_dir() else None

    def reminder_due(self, today: date, data_since: date | None) -> bool:
        """Whether to remind the user to save a copy outside the computer.

        From the last days of the month, when that month has no such copy, and on into the
        next month until there is one or the user puts it off. Data newer than the
        reminder (``data_since``, the first account) waits for the next month's end.
        """
        start = reminder_start(today)
        if not self._settings.backup_reminder() or data_since is None or data_since >= start:
            return False
        last = self._settings.last_external_backup()
        if last is not None and last >= start.replace(day=1):
            return False
        return self._settings.backup_reminder_dismissed() != f"{start:%Y-%m}"

    def put_off_reminder(self, today: date) -> None:
        """«Ahora no»: silent until the next month's end."""
        self._settings.set_backup_reminder_dismissed(f"{reminder_start(today):%Y-%m}")

    def restore(self, source: Path, now: datetime) -> None:
        """Replaces the current data with the copy at ``source``.

        The current data is copied first, so a restore can itself be undone.
        """
        try:
            version = Database.inspect(source)
        except DatabaseError as error:
            raise ValidationError("El archivo no es una copia válida de Nodus.") from error
        if version == 0:
            raise ValidationError("El archivo no es una copia de Nodus.")
        if version > latest_schema_version():
            raise ValidationError(
                "La copia viene de una versión más nueva de Nodus. Actualiza Nodus para usarla."
            )
        self._copy_to(self.backups_dir / f"nodus-antes-de-restaurar-{now:%Y-%m-%d-%H%M}.db")
        self._database.restore_from(source)

    def _copy_to(self, destination: Path) -> None:
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self._database.backup_to(destination)

    def _daily_backups(self) -> list[tuple[date, Path]]:
        """Daily backups, oldest first. Copies taken before a restore are not counted."""
        if not self.backups_dir.is_dir():
            return []
        found = []
        for path in self.backups_dir.iterdir():
            match = _DAILY_NAME.match(path.name)
            if match:
                found.append((date.fromisoformat(match.group(1)), path))
        return sorted(found)

    def _prune(self) -> None:
        for _day, path in self._daily_backups()[: -self.KEEP]:
            path.unlink()
