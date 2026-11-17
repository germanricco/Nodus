"""Daily copies of the user's database, copies saved outside the computer, and restoring
from one of them."""

from __future__ import annotations

import calendar
import logging
import re
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from nodus.config.paths import AppPaths
from nodus.database.database import (
    Database,
    DatabaseError,
    backup_path_for,
    latest_schema_version,
)
from nodus.services.app.settings_service import SettingsService
from nodus.services.errors import BackupError, ValidationError

logger = logging.getLogger(__name__)

# A copy is named after its day; ``_DAILY_NAME`` reads the day back, for the old ones.
_DAILY_NAME = re.compile(r"^nodus-(\d{4}-\d{2}-\d{2})\.db$")


def daily_name(day: date) -> str:
    """ "nodus-2026-11-17.db": the copy of ``day``, in the computer or outside it."""
    return f"nodus-{day.isoformat()}.db"


def daily_backups(folder: Path) -> list[tuple[date, Path]]:
    """The daily copies in ``folder``, oldest first. A name that is not a real day, like
    a copy renamed by hand to «nodus-2026-02-30.db», is not one of them."""
    if not folder.is_dir():
        return []
    found = []
    for path in folder.iterdir():
        match = _DAILY_NAME.match(path.name)
        if match:
            try:
                found.append((date.fromisoformat(match.group(1)), path))
            except ValueError:
                continue
    return sorted(found)


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
        destination = self.backups_dir / daily_name(today)
        try:
            self._copy_to(destination)
        except (OSError, sqlite3.Error) as error:
            logger.warning("Backup failed", exc_info=error)
            raise BackupError(str(error)) from error
        logger.info("Backup saved")
        self._prune()
        self.last_error = None  # a copy made by hand mends the day's failed one
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
        except BackupError:
            # The system's text stays out of a notice; «Hacer copia» shows it, if it fails again.
            self.last_error = (
                "No se pudo hacer la copia del día. Revisa que quede lugar en el disco y toca"
                " «Hacer copia» en Ajustes."
            )
            return None
        return backup

    def last_backup(self) -> date | None:
        """The day of the newest daily copy, if there is one."""
        days = self._daily_backups()
        return days[-1][0] if days else None

    def export_to(self, folder: Path, today: date) -> Path:
        """Saves a copy of the data in ``folder``, outside the computer, and remembers the
        day and the folder, which is offered again the next time.

        Raises ``BackupError`` if the copy cannot be written (a pen drive taken out).
        """
        destination = folder / daily_name(today)
        try:
            self._database.backup_to(destination)
        except (OSError, sqlite3.Error) as error:
            logger.warning("Copy outside the computer failed", exc_info=error)
            raise BackupError(str(error)) from error
        logger.info("Copy saved outside the computer")
        self._settings.set_external_backup(today, folder)
        return destination

    def last_external_backup(self) -> date | None:
        """The day of the last copy saved outside the computer, if any."""
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
            logger.warning("Restore refused: not a readable database", exc_info=error)
            raise ValidationError("El archivo no es una copia válida de Nodus.") from error
        if version == 0:
            logger.warning("Restore refused: an empty database")
            raise ValidationError("El archivo no es una copia de Nodus.")
        if version > latest_schema_version():
            logger.warning("Restore refused: schema %d is newer than this Nodus", version)
            raise ValidationError(
                "La copia viene de una versión más nueva de Nodus. Actualiza Nodus para usarla."
            )
        self._copy_to(self.backups_dir / f"nodus-antes-de-restaurar-{now:%Y-%m-%d-%H%M}.db")
        self._database.restore_from(source)
        logger.info("Copy restored: schema %d", version)

    def _copy_to(self, destination: Path) -> None:
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self._database.backup_to(destination)

    def _daily_backups(self) -> list[tuple[date, Path]]:
        """Daily backups, oldest first. Copies taken before a restore are not counted."""
        return daily_backups(self.backups_dir)

    def _prune(self) -> None:
        """Deletes the oldest daily copies. One that cannot be deleted (an antivirus is
        reading it) stays until next time: the new copy is saved all the same."""
        for _day, path in self._daily_backups()[: -self.KEEP]:
            try:
                path.unlink()
            except OSError as error:
                logger.warning("An old backup could not be deleted", exc_info=error)


@dataclass(frozen=True)
class RecoveryCopy:
    """A copy whole enough to bring the data back from, and when it was saved."""

    path: Path
    saved: datetime


class DataRecovery:
    """Brings the data back from the newest whole copy when the data file is damaged.

    Works on paths, before any ``Database`` is open, since the damaged file cannot be
    opened. The damaged file is moved aside, never deleted: what it still holds may be
    rescued by hand.
    """

    def __init__(self, paths: AppPaths) -> None:
        self._paths = paths

    def newest_copy(self) -> RecoveryCopy | None:
        """The newest copy that opens whole in this Nodus: a daily one, one taken before a
        restore, or the one taken before updating the data."""
        candidates = [*self._paths.backups_dir.glob("*.db")]
        before_update = backup_path_for(self._paths.database_path)
        if before_update.exists():
            candidates.append(before_update)
        for path in sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True):
            if _is_whole(path):
                return RecoveryCopy(path, datetime.fromtimestamp(path.stat().st_mtime))
        return None

    def recover(self, copy: RecoveryCopy, now: datetime) -> Path:
        """Moves the damaged file aside, with its WAL, and puts ``copy`` in its place.

        Returns where the damaged file went.
        """
        database_path = self._paths.database_path
        damaged = database_path.with_name(f"nodus-dañado-{now:%Y-%m-%d-%H%M%S}.db")
        for suffix in ("", "-wal", "-shm"):
            source = database_path.with_name(database_path.name + suffix)
            if source.exists():
                source.replace(damaged.with_name(damaged.name + suffix))
        shutil.copyfile(copy.path, database_path)
        logger.info("Data recovered from a copy; the damaged file was moved aside")
        return damaged


def _is_whole(path: Path) -> bool:
    try:
        version = Database.inspect(path)
    except DatabaseError:
        return False
    return 0 < version <= latest_schema_version()
