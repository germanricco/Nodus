"""Daily copies of the user's database, and restoring from one of them."""

from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime
from pathlib import Path

from nodus.database.database import Database, DatabaseError, latest_schema_version
from nodus.services.errors import ValidationError

_DAILY_NAME = re.compile(r"^nodus-(\d{4}-\d{2}-\d{2})\.db$")


class BackupService:
    """Keeps one copy of the data per day in ``backups_dir``, up to ``KEEP`` of them.

    The data lives in a single file the user may never think about backing up; a copy a
    day costs a few KB and turns a mistake (or a damaged file) into a short trip back.
    """

    KEEP = 10

    def __init__(self, database: Database, backups_dir: Path) -> None:
        self._database = database
        self.backups_dir = backups_dir
        self.last_error: str | None = None

    def create(self, today: date) -> Path:
        """Copies the data to today's backup, replacing an earlier one from today."""
        destination = self.backups_dir / f"nodus-{today.isoformat()}.db"
        self._copy_to(destination)
        self._prune()
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
        except (OSError, sqlite3.Error) as error:
            self.last_error = f"No se pudo hacer la copia del día: {error}"
            return None
        self.last_error = None
        return backup

    def last_backup(self) -> date | None:
        days = self._daily_backups()
        return days[-1][0] if days else None

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
