import sqlite3
from datetime import date, datetime, timedelta

import pytest
from factories import ars

from nodus.database.database import Database, Migration, latest_schema_version
from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.services.backup_service import BackupService, reminder_start
from nodus.services.errors import BackupError, ValidationError

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
    assert "disco lleno" in services.backups.last_error


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
