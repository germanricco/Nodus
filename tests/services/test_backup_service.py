import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from factories import ars, services_for

from nodus.config.paths import AppPaths
from nodus.database.database import Database, Migration, latest_schema_version
from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.services.backup_service import BackupService, DataRecovery, reminder_start
from nodus.services.errors import BackupError, ValidationError

# Not factories.TODAY: the copies below are named after this day.
TODAY = date(2026, 11, 6)
NOW = datetime(2026, 11, 6, 21, 30)


def account_names(services) -> list[str]:
    return [account.name for account in services.accounts.list_accounts()]


def add_account(services, name: str) -> None:
    services.accounts.create(name, AccountType.CASH, Currency.ARS, ars("1000"))


def test_create_names_backup_by_day(services):
    backup = services.backups.create(TODAY)

    assert backup.name == "nodus-2026-11-06.db"
    assert backup.parent == services.backups.backups_dir
    assert services.backups.last_backup() == TODAY


def test_backup_holds_the_current_data(services):
    add_account(services, "Banco")

    backup = services.backups.create(TODAY)

    copy = sqlite3.connect(backup)
    assert copy.execute("SELECT name FROM accounts").fetchall() == [("Banco",)]
    copy.close()


def test_keeps_only_the_latest_backups(services):
    for offset in range(BackupService.KEEP + 3):
        services.backups.create(TODAY + timedelta(days=offset))

    names = sorted(p.name for p in services.backups.backups_dir.iterdir())

    assert len(names) == BackupService.KEEP
    assert names[0] == "nodus-2026-11-09.db"


def test_create_if_due_makes_one_backup_per_day(services):
    assert services.backups.create_if_due(TODAY) is not None
    assert services.backups.create_if_due(TODAY) is None
    assert services.backups.create_if_due(TODAY + timedelta(days=1)) is not None


def test_failed_daily_backup_is_remembered_not_raised(services, monkeypatch):
    def broken(_destination):
        raise OSError("disco lleno")

    monkeypatch.setattr(services.backups, "_copy_to", broken)

    assert services.backups.create_if_due(TODAY) is None
    assert services.backups.last_error.startswith("No se pudo hacer la copia del día.")
    assert "disco lleno" not in services.backups.last_error


@pytest.mark.parametrize("failure", [OSError("disco lleno"), sqlite3.Error("base bloqueada")])
def test_failed_backup_raises_a_backup_error(services, monkeypatch, failure):
    """The caller sees one service error, whatever failed underneath."""

    def broken(_destination):
        raise failure

    monkeypatch.setattr(services.backups, "_copy_to", broken)

    with pytest.raises(BackupError, match=str(failure)):
        services.backups.create(TODAY)


def test_restore_brings_back_the_copy_and_saves_current_data(services):
    add_account(services, "Banco")
    backup = services.backups.create(TODAY)
    add_account(services, "Efectivo")

    services.backups.restore(backup, NOW)

    assert account_names(services) == ["Banco"]
    before = services.backups.backups_dir / "nodus-antes-de-restaurar-2026-11-06-2130.db"
    assert before.exists()


@pytest.mark.parametrize("content", [b"no soy una base", b""])
def test_restore_rejects_files_that_are_not_nodus_copies(services, tmp_path, content):
    add_account(services, "Banco")
    bogus = tmp_path / "bogus.db"
    bogus.write_bytes(content)

    with pytest.raises(ValidationError):
        services.backups.restore(bogus, NOW)

    assert account_names(services) == ["Banco"]


def test_restore_rejects_copies_from_a_newer_nodus(services, tmp_path):
    newer = tmp_path / "newer.db"
    connection = sqlite3.connect(newer)
    connection.execute(f"PRAGMA user_version = {latest_schema_version() + 1}")
    connection.close()

    with pytest.raises(ValidationError, match="más nueva"):
        services.backups.restore(newer, NOW)


def test_restored_older_copy_is_migrated(tmp_path):
    older = tmp_path / "older.db"
    Database.open(older, [Migration(1, "base", "CREATE TABLE notes (text TEXT);")]).close()
    current = Database.open(
        tmp_path / "current.db",
        [
            Migration(1, "base", "CREATE TABLE notes (text TEXT);"),
            Migration(2, "more", "ALTER TABLE notes ADD COLUMN day TEXT;"),
        ],
    )

    current.restore_from(
        older,
        [
            Migration(1, "base", "CREATE TABLE notes (text TEXT);"),
            Migration(2, "more", "ALTER TABLE notes ADD COLUMN day TEXT;"),
        ],
    )

    assert current.schema_version == 2
    columns = [row[1] for row in current.connection.execute("PRAGMA table_info(notes)")]
    assert columns == ["text", "day"]
    current.close()


class TestCopyOutside:
    def test_is_saved_in_the_folder_and_remembered(self, services, tmp_path):
        copy = services.backups.export_to(tmp_path, TODAY)

        assert copy == tmp_path / "nodus-2026-11-06.db"
        assert copy.is_file()
        assert services.backups.last_external_backup() == TODAY
        assert services.backups.external_folder() == tmp_path

    def test_can_be_restored(self, services, tmp_path):
        add_account(services, "Banco")
        copy = services.backups.export_to(tmp_path, TODAY)
        add_account(services, "Efectivo")

        services.backups.restore(copy, NOW)

        assert account_names(services) == ["Banco"]

    def test_to_a_missing_folder_fails_and_remembers_nothing(self, services, tmp_path):
        with pytest.raises(BackupError):
            services.backups.export_to(tmp_path / "pendrive-sacado", TODAY)

        assert services.backups.last_external_backup() is None

    def test_the_last_folder_is_offered_only_while_it_is_there(self, services, tmp_path):
        pen_drive = tmp_path / "E"
        pen_drive.mkdir()
        services.backups.export_to(pen_drive, TODAY)

        pen_drive.joinpath("nodus-2026-11-06.db").unlink()
        pen_drive.rmdir()

        assert services.backups.external_folder() is None


@pytest.mark.parametrize(
    ("today", "start"),
    [
        (date(2026, 11, 28), date(2026, 11, 28)),  # 30 days: the last three are 28 to 30
        (date(2026, 11, 30), date(2026, 11, 28)),
        (date(2026, 11, 27), date(2026, 10, 29)),  # before it, the month before's
        (date(2026, 12, 3), date(2026, 11, 28)),
        (date(2027, 2, 26), date(2027, 2, 26)),  # 28 days
        (date(2027, 1, 15), date(2026, 12, 29)),  # across the year
    ],
)
def test_reminder_starts_three_days_before_the_month_ends(today, start):
    assert reminder_start(today) == start


def test_a_copy_named_after_an_impossible_day_is_not_a_daily_copy(services):
    services.backups.backups_dir.mkdir(parents=True)
    (services.backups.backups_dir / "nodus-2026-02-30.db").write_bytes(b"")

    assert services.backups.last_backup() is None
    assert services.backups.create_if_due(TODAY) is not None
    assert services.backups.last_backup() == TODAY


def test_an_old_copy_that_cannot_be_deleted_does_not_fail_the_new_one(services, monkeypatch):
    for days in range(BackupService.KEEP):
        services.backups.create(TODAY - timedelta(days=days + 1))
    real_unlink = Path.unlink

    def held_by_antivirus(path, *args, **kwargs):
        if path.parent == services.backups.backups_dir:
            raise PermissionError("in use")
        real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", held_by_antivirus)

    assert services.backups.create_if_due(TODAY) is not None
    assert services.backups.last_error is None
    assert services.backups.last_backup() == TODAY


class TestDataRecovery:
    """Bringing damaged data back from the newest copy that is whole."""

    @pytest.fixture
    def paths(self, tmp_path) -> AppPaths:
        paths = AppPaths(tmp_path / "Nodus")
        paths.ensure_data_dir()
        paths.backups_dir.mkdir()
        return paths

    def copy_with(self, path: Path, account: str, age: int) -> Path:
        """A copy at ``path`` holding ``account``, saved ``age`` hours ago."""
        database = Database.open(path)
        add_account(services_for(database), account)
        database.close()
        saved = NOW.timestamp() - age * 3600
        os.utime(path, (saved, saved))
        return path

    def test_the_newest_whole_copy_is_chosen(self, paths):
        self.copy_with(paths.backups_dir / "nodus-2026-11-04.db", "Vieja", age=48)
        newest = self.copy_with(paths.backups_dir / "nodus-2026-11-05.db", "Nueva", age=24)

        copy = DataRecovery(paths).newest_copy()

        assert copy.path == newest
        assert copy.saved == NOW - timedelta(hours=24)

    def test_a_damaged_or_newer_copy_is_skipped(self, paths):
        whole = self.copy_with(paths.backups_dir / "nodus-2026-11-03.db", "Sana", age=72)
        damaged = paths.backups_dir / "nodus-2026-11-05.db"
        damaged.write_bytes(b"not a database" * 100)
        newer = self.copy_with(paths.backups_dir / "nodus-2026-11-04.db", "Nueva", age=48)
        raw = sqlite3.connect(newer)
        raw.execute(f"PRAGMA user_version = {latest_schema_version() + 1}")
        raw.close()

        assert DataRecovery(paths).newest_copy().path == whole

    def test_the_copy_taken_before_updating_counts(self, paths):
        before_update = paths.database_path.with_name("nodus.db.bak")
        self.copy_with(before_update, "Antes de actualizar", age=1)

        assert DataRecovery(paths).newest_copy().path == before_update

    def test_without_copies_there_is_nothing_to_recover(self, paths):
        assert DataRecovery(paths).newest_copy() is None

    def test_recovering_moves_the_damaged_file_aside_with_its_wal(self, paths):
        copy = self.copy_with(paths.backups_dir / "nodus-2026-11-05.db", "Nueva", age=1)
        paths.database_path.write_bytes(b"damaged")
        paths.database_path.with_name("nodus.db-wal").write_bytes(b"wal")
        recovery = DataRecovery(paths)

        aside = recovery.recover(recovery.newest_copy(), NOW)

        assert aside.name == "nodus-dañado-2026-11-06-213000.db"
        assert aside.read_bytes() == b"damaged"
        assert aside.with_name(aside.name + "-wal").read_bytes() == b"wal"
        assert not paths.database_path.with_name("nodus.db-wal").exists()
        assert paths.database_path.read_bytes() == copy.read_bytes()
