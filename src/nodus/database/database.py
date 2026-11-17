"""SQLite connection and schema migrations."""

from __future__ import annotations

import logging
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

logger = logging.getLogger(__name__)

_MIGRATIONS_PACKAGE = "nodus.database.migrations"
_MIGRATION_FILENAME = re.compile(r"^(\d+)_(\w+)\.sql$")


class DatabaseError(Exception):
    """The database file could not be opened, verified or migrated. Raised as such when
    the file could not be reached at all (locked by another program, no permission)."""


class DamagedDatabaseError(DatabaseError):
    """The file is not a whole SQLite database: its data can only come back from a copy."""


class NewerDatabaseError(DatabaseError):
    """The file was written by a newer Nodus, whose tables this one does not know."""


class MigrationError(DatabaseError):
    """Updating the file to this version of Nodus failed. The file stays at the last
    version that succeeded; it is a fault of Nodus, not of the file."""


@dataclass(frozen=True)
class Migration:
    """One schema change. ``version`` becomes the database's ``user_version`` once applied."""

    version: int
    name: str
    sql: str


class Database:
    """Owns the connection to the user's SQLite file and keeps its schema up to date.

    Use ``Database.open`` rather than the constructor: it also verifies the file's integrity
    and applies pending migrations, so callers always get a ready-to-use database.
    """

    def __init__(self, path: Path, connection: sqlite3.Connection) -> None:
        self.path = path
        self._connection = connection
        # True when this run created the file, so the app can tell a first start from
        # an update (both lack settings written by newer versions).
        self.created = False

    @classmethod
    def open(cls, path: Path, migrations: list[Migration] | None = None) -> Database:
        """Opens (or creates) the database at ``path``, verifies it and migrates it.

        ``migrations`` defaults to the SQL files packaged in ``nodus.database.migrations``.
        Each way of failing raises its own ``DatabaseError``, since each asks the user for
        something different, and leaves the file closed, so it can be moved aside.
        """
        migrations = migrations if migrations is not None else load_packaged_migrations()
        try:
            database = cls(path, cls._connect(path))
        except sqlite3.DatabaseError as error:
            raise _opening_error(path, error) from error
        try:
            database._verify(migrations)
            try:
                database.migrate(migrations)
            except (sqlite3.Error, DatabaseError, OSError) as error:
                raise MigrationError(f"{path}: {error}") from error
        except BaseException:
            database.close()
            raise
        logger.info(
            "Data opened: schema %d%s", database.schema_version, ", new" if database.created else ""
        )
        return database

    @staticmethod
    def _connect(path: Path) -> sqlite3.Connection:
        connection = sqlite3.connect(path)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            # WAL keeps the file consistent if the app or the OS crashes mid-write.
            connection.execute("PRAGMA journal_mode = WAL")
        except sqlite3.Error:
            connection.close()
            raise
        return connection

    def _verify(self, migrations: list[Migration]) -> None:
        try:
            self.check_integrity()
            version = self.schema_version
        except sqlite3.DatabaseError as error:
            raise _opening_error(self.path, error) from error
        newest = max((migration.version for migration in migrations), default=0)
        if version > newest:
            raise NewerDatabaseError(f"{self.path}: schema {version}, this Nodus knows {newest}")
        self.created = version == 0

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Groups writes so they are all saved together or not at all.

        Repositories never commit on their own; services wrap each operation in this block,
        so a multi-step change (like the two legs of a transfer) cannot be half-saved.
        """
        with self._connection:
            yield self._connection

    @property
    def schema_version(self) -> int:
        return self._connection.execute("PRAGMA user_version").fetchone()[0]

    def check_integrity(self) -> None:
        result = self._connection.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise DamagedDatabaseError(f"{self.path}: integrity check failed: {result}")

    def migrate(self, migrations: list[Migration]) -> None:
        """Applies, in order, every migration newer than the current schema version.

        An existing database is backed up first, since a migration rewrites user data.
        Each migration runs in its own transaction: if it fails, the schema stays at the
        last version that succeeded.
        """
        pending = sorted(
            (m for m in migrations if m.version > self.schema_version), key=lambda m: m.version
        )
        if not pending:
            return
        logger.info(
            "Updating the data from schema %d to %d", self.schema_version, pending[-1].version
        )
        if self.schema_version > 0:
            self.backup_to(self.backup_path)
        for migration in pending:
            self._apply(migration)

    @property
    def backup_path(self) -> Path:
        return backup_path_for(self.path)

    def backup_to(self, destination: Path) -> None:
        """Copies the whole database, including changes still in the WAL file."""
        target = sqlite3.connect(destination)
        try:
            self._connection.backup(target)
        finally:
            target.close()

    def restore_from(self, source: Path, migrations: list[Migration] | None = None) -> None:
        """Replaces every table with the contents of the database file ``source``.

        Works on the open connection, so the app keeps running; a copy made by an older
        Nodus is then migrated like any other database.
        """
        copy = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
        try:
            copy.backup(self._connection)
        finally:
            copy.close()
        self.migrate(migrations if migrations is not None else load_packaged_migrations())

    @staticmethod
    def inspect(path: Path) -> int:
        """Schema version of the database file at ``path``, after checking its integrity.

        Raises DatabaseError if the file is not a readable SQLite database.
        """
        try:
            connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
            try:
                if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise DatabaseError(f"{path}: integrity check failed")
                return connection.execute("PRAGMA user_version").fetchone()[0]
            finally:
                connection.close()
        except sqlite3.DatabaseError as error:
            raise DatabaseError(f"{path}: {error}") from error

    def _apply(self, migration: Migration) -> None:
        """Runs ``migration`` in one transaction, with foreign keys off as SQLite requires to
        rebuild a table others refer to (dropping it would otherwise cascade or fail).

        The keys are checked before committing, so a migration can never leave a row
        pointing nowhere.
        """
        connection = self._connection
        connection.execute("PRAGMA foreign_keys = OFF")  # has no effect inside a transaction
        try:
            connection.executescript(f"BEGIN;\n{migration.sql}")
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise DatabaseError(
                    f"Migration {migration.version} would break references between tables."
                )
            connection.execute(f"PRAGMA user_version = {migration.version}")
            connection.commit()
        except (sqlite3.Error, DatabaseError):
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        """Closes the file, with every change moved from the WAL into it, so ``nodus.db``
        is whole by itself when the user copies it."""
        try:
            self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error as error:  # another reader: the WAL is kept, nothing is lost
            logger.warning("The data was closed with changes still in the WAL", exc_info=error)
        self._connection.close()


def backup_path_for(database_path: Path) -> Path:
    """Where ``migrate`` keeps the copy taken before updating the file at ``database_path``."""
    return database_path.with_name(database_path.name + ".bak")


def _opening_error(path: Path, error: sqlite3.DatabaseError) -> DatabaseError:
    """What an SQLite error while opening means: ``OperationalError`` is the file being out
    of reach (locked, no permission); the rest («file is not a database», «malformed»)
    is the file being damaged."""
    if isinstance(error, sqlite3.OperationalError):
        return DatabaseError(f"{path}: {error}")
    return DamagedDatabaseError(f"{path}: {error}")


def load_packaged_migrations() -> list[Migration]:
    """Reads the ``NNN_name.sql`` files shipped inside the package."""
    migrations = []
    for entry in resources.files(_MIGRATIONS_PACKAGE).iterdir():
        match = _MIGRATION_FILENAME.match(entry.name)
        if match:
            version, name = match.groups()
            migrations.append(Migration(int(version), name, entry.read_text(encoding="utf-8")))
    return migrations


def latest_schema_version() -> int:
    """The schema version this build of Nodus migrates databases to."""
    return max(migration.version for migration in load_packaged_migrations())
