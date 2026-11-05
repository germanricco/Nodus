"""SQLite connection and schema migrations."""

from __future__ import annotations

import re
import sqlite3
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

    @classmethod
    def open(cls, path: Path, migrations: list[Migration] | None = None) -> Database:
        """Opens (or creates) the database at ``path``, verifies it and migrates it.

        ``migrations`` defaults to the SQL files packaged in ``nodus.database.migrations``.
        """
        try:
            database = cls(path, cls._connect(path))
            database.check_integrity()
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

    def _apply(self, migration: Migration) -> None:
        script = f"BEGIN;\n{migration.sql}\nPRAGMA user_version = {migration.version};\nCOMMIT;"
        try:
            self._connection.executescript(script)
        except sqlite3.Error:
            if self._connection.in_transaction:
                self._connection.rollback()
            raise

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
