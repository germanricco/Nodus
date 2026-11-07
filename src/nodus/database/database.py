"""SQLite connection and schema migrations."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

_MIGRATIONS_PACKAGE = "nodus.database.migrations"
_MIGRATION_FILENAME = re.compile(r"^(\d+)_(\w+)\.sql$")


class DatabaseError(Exception):
    """The database file could not be opened, verified or migrated."""


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
        """
        try:
            database = cls(path, cls._connect(path))
            database.check_integrity()
            database.created = database.schema_version == 0
            database.migrate(migrations if migrations is not None else load_packaged_migrations())
        except sqlite3.DatabaseError as error:
            raise DatabaseError(f"{path}: {error}") from error
        return database

    @staticmethod
    def _connect(path: Path) -> sqlite3.Connection:
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        # WAL keeps the file consistent if the app or the OS crashes mid-write.
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

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
            raise DatabaseError(f"{self.path}: integrity check failed: {result}")

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
        if self.schema_version > 0:
            self.backup_to(self.backup_path)
        for migration in pending:
            self._apply(migration)

    @property
    def backup_path(self) -> Path:
        return self.path.with_name(self.path.name + ".bak")

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
        self._connection.close()


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
