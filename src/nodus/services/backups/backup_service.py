"""Daily copies of the user's data, copies saved outside the computer, copies taken
before deleting, and restoring from any of them."""

from __future__ import annotations

import calendar
import logging
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from nodus.database.database import Database, DatabaseError
from nodus.i18n import _
from nodus.services.app.settings_service import SettingsService
from nodus.services.app.undo_service import UndoService
from nodus.services.backups import restore, retention
from nodus.services.errors import BackupError

logger = logging.getLogger(__name__)

# A copy is named after its day; ``_DAILY_NAME`` reads the day back, for the old ones.
_DAILY_NAME = re.compile(r"^nodus-(\d{4}-\d{2}-\d{2})\.db$")
# A copy taken before restoring or deleting, named after the moment it was taken.
_ONE_OFF_NAME = re.compile(r"^nodus-antes-de-(?:restaurar|borrar)-(\d{4}-\d{2}-\d{2})-\d+\.db$")


def daily_name(day: date) -> str:
    """ "nodus-2026-11-17.db": the copy of ``day``, in the computer or outside it."""
    return f"nodus-{day.isoformat()}.db"


def daily_backups(folder: Path) -> list[tuple[date, Path]]:
    """The daily copies in ``folder``, oldest first. A name that is not a real day, like
    a copy renamed by hand to «nodus-2026-02-30.db», is not one of them."""
    return _dated(folder, _DAILY_NAME)


def one_off_backups(folder: Path) -> list[tuple[date, Path]]:
    """The copies taken before restoring or deleting, oldest first, by their day."""
    return _dated(folder, _ONE_OFF_NAME)


def _dated(folder: Path, name: re.Pattern[str]) -> list[tuple[date, Path]]:
    if not folder.is_dir():
        return []
    found = []
    for path in folder.iterdir():
        match = name.match(path.name)
        if match:
            try:
                found.append((date.fromisoformat(match.group(1)), path))
            except ValueError:
                continue
    return sorted(found)


# Deleting this many movements at once copies the data first, as deleting an account or a
# category always does.
LARGE_DELETE = 20

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
    """Keeps one copy of the data per day in ``backups_dir``, for as long as
    ``retention`` says.

    The data lives in a single file the user may never think about backing up; a copy a
    day costs a few KB and turns a mistake (or a damaged file) into a short trip back.

    Those copies share the computer's disk, so losing the computer loses them too. Once a
    month, Nodus reminds the user to save one outside it: a pen drive, an external disk or
    a folder that syncs to Drive or OneDrive.
    """

    def __init__(
        self,
        database: Database,
        backups_dir: Path,
        settings: SettingsService,
        undo: UndoService,
    ) -> None:
        self._database = database
        self.backups_dir = backups_dir
        self._settings = settings
        self._undo = undo
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
        self._prune(today)
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
            self.last_error = _(
                "No se pudo hacer la copia del día. Revisa que quede lugar en el disco "
                "y toca «Hacer copia» en Ajustes."
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

        The copy is written as «….db.part» and gets its name only once it reads back
        whole, so a pen drive taken out halfway never holds a broken copy with a good
        name. Raises ``BackupError`` if the copy cannot be written.
        """
        destination = folder / daily_name(today)
        partial = destination.with_name(destination.name + ".part")
        try:
            self._database.backup_to(partial)
            Database.check_copy(partial)
            partial.replace(destination)
        except (OSError, sqlite3.Error, DatabaseError) as error:
            logger.warning("Copy outside the computer failed", exc_info=error)
            _delete_quietly(partial)
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
        """Replaces the current data with the copy at ``source``, once ``restore`` has
        updated and checked it whole on a file of its own.

        The current data is copied first, so a restore can itself be undone, and the last
        «Deshacer» is forgotten: it belongs to data that is no longer there. Raises
        ``ValidationError`` when ``source`` is not a whole copy of Nodus and
        ``BackupError`` when a file cannot be written; the data stays as it was.
        """
        work_dir = self._database.path.parent
        prepared = restore.prepared_copy(source, work_dir)
        try:
            self._copy_to(self.backups_dir / f"nodus-antes-de-restaurar-{now:%Y-%m-%d-%H%M}.db")
            self._database.replace_with(prepared)
        except (OSError, sqlite3.Error) as error:
            logger.warning("Restore failed; the data stays as it was", exc_info=error)
            raise BackupError(str(error)) from error
        finally:
            prepared.close()
            restore.discard(work_dir)
        self._undo.forget()
        logger.info("Copy restored")

    def create_before_delete(self, now: datetime) -> None:
        """Copies the data before a large deletion (an account, a category, many
        movements), kept for a month. Deleting was confirmed already, so a copy that
        cannot be written is only logged: it does not stop the deletion."""
        destination = self.backups_dir / f"nodus-antes-de-borrar-{now:%Y-%m-%d-%H%M%S}.db"
        try:
            self._copy_to(destination)
        except (OSError, sqlite3.Error) as error:
            logger.warning("The copy before deleting failed", exc_info=error)
            return
        logger.info("Copy saved before deleting")
        self._prune(now.date())

    def _copy_to(self, destination: Path) -> None:
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self._database.backup_to(destination)

    def _daily_backups(self) -> list[tuple[date, Path]]:
        """Daily backups, oldest first. Copies taken before a restore are not counted."""
        return daily_backups(self.backups_dir)

    def _prune(self, today: date) -> None:
        """Deletes the copies ``retention`` no longer keeps. One that cannot be deleted
        (an antivirus is reading it) stays until next time: the new copy is saved all
        the same."""
        daily = self._daily_backups()
        kept = retention.kept_days([day for day, _path in daily])
        doomed = [path for day, path in daily if day not in kept]
        doomed += [
            path
            for day, path in one_off_backups(self.backups_dir)
            if retention.one_off_expired(day, today)
        ]
        for path in doomed:
            try:
                path.unlink()
            except OSError as error:
                logger.warning("An old backup could not be deleted", exc_info=error)


def _delete_quietly(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        logger.warning("A partial copy could not be deleted", exc_info=error)
