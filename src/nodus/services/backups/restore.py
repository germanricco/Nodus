"""Restoring a copy without risking the data in use.

The copy is brought to a file of its own beside the data, updated there to this version
of Nodus and checked whole: integrity, every table this version needs, and every row
pointing to one that exists. Only a copy that passes all of it replaces the data, in one
step, so a broken copy or a full disk halfway through leaves the data as it was.
"""

from __future__ import annotations

import logging
from pathlib import Path

from nodus.database.database import (
    Database,
    DatabaseError,
    MigrationError,
    latest_schema_version,
    latest_table_names,
    migration_backups,
)
from nodus.services.errors import BackupError, ValidationError

logger = logging.getLogger(__name__)

WORK_NAME = "nodus-restaurando.db"
NOT_A_COPY_TEXT = "El archivo no es una copia de Nodus."
UNREADABLE_TEXT = "El archivo no es una copia válida de Nodus."
NEWER_TEXT = "La copia viene de una versión más nueva de Nodus. Actualiza Nodus para usarla."
INCOMPLETE_TEXT = "La copia está incompleta o dañada."


def prepared_copy(source: Path, work_dir: Path) -> Database:
    """``source`` as an open database on a file of its own in ``work_dir``, updated and
    checked; the caller closes it and calls ``discard``.

    Raises ``ValidationError`` when the file is not a whole copy of Nodus, and
    ``BackupError`` when the work file cannot be written (a full disk).
    """
    _require_copy_of_nodus(source)
    work = work_dir / WORK_NAME
    discard(work_dir)
    try:
        Database.copy_file(source, work)
    except DatabaseError as error:
        discard(work_dir)
        logger.warning("Restore refused: the copy could not be read", exc_info=error)
        raise ValidationError(UNREADABLE_TEXT) from error
    except OSError as error:
        discard(work_dir)
        raise BackupError(str(error)) from error
    try:
        database = Database.open(work)
    except MigrationError as error:
        discard(work_dir)
        logger.error("Restore refused: the copy could not be updated", exc_info=error)
        raise ValidationError(INCOMPLETE_TEXT) from error
    except DatabaseError as error:
        discard(work_dir)
        logger.warning("Restore refused: the copy is damaged", exc_info=error)
        raise ValidationError(INCOMPLETE_TEXT) from error
    missing = latest_table_names() - database.table_names()
    if missing or not database.foreign_keys_hold():
        database.close()
        discard(work_dir)
        logger.warning("Restore refused: %d tables missing or broken references", len(missing))
        raise ValidationError(INCOMPLETE_TEXT)
    return database


def discard(work_dir: Path) -> None:
    """Deletes what ``prepared_copy`` left in ``work_dir``, including one left by a
    restore that Nodus closed halfway through."""
    work = work_dir / WORK_NAME
    leftovers = [work.with_name(work.name + suffix) for suffix in ("", "-wal", "-shm")]
    for path in [*leftovers, *migration_backups(work)]:
        try:
            path.unlink(missing_ok=True)
        except OSError as error:  # deleted next time; it is never mistaken for the data
            logger.warning("A restore's work file could not be deleted", exc_info=error)


def _require_copy_of_nodus(source: Path) -> None:
    try:
        version = Database.inspect(source)
    except DatabaseError as error:
        logger.warning("Restore refused: not a readable database", exc_info=error)
        raise ValidationError(UNREADABLE_TEXT) from error
    if version == 0:
        logger.warning("Restore refused: an empty database")
        raise ValidationError(NOT_A_COPY_TEXT)
    if version > latest_schema_version():
        logger.warning("Restore refused: schema %d is newer than this Nodus", version)
        raise ValidationError(NEWER_TEXT)
