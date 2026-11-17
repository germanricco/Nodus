"""Bringing the data back from a copy when the data file itself is damaged."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from nodus.config.paths import AppPaths
from nodus.database.database import (
    Database,
    DatabaseError,
    latest_schema_version,
    migration_backups,
)

logger = logging.getLogger(__name__)


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
        candidates += migration_backups(self._paths.database_path)
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
