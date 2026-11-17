"""Restoring a copy: only a whole copy replaces the data, and nothing old is undone over it."""

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest
from factories import TODAY, ars, charge_draft, expense_draft

from nodus.database.database import Database, migration_backups
from nodus.services.app.undo_service import UndoError
from nodus.services.backups import restore
from nodus.services.errors import BackupError, ValidationError

NOW = datetime(2026, 11, 5, 10, 30)


@pytest.fixture
def copy(services, pesos, tmp_path) -> Path:
    """A copy outside the computer holding the account «Banco»; the data then moves on."""
    saved = services.backups.export_to(tmp_path, TODAY)
    services.accounts.update(pesos.id, "Cambiado", pesos.type, pesos.initial_balance)
    return saved


def account_names(services) -> list[str]:
    return [account.name for account in services.accounts.list_accounts()]


def work_files(services) -> list[str]:
    folder = services.transactions._database.path.parent
    return sorted(p.name for p in folder.iterdir() if p.name.startswith(restore.WORK_NAME))


def test_a_whole_copy_replaces_the_data_and_leaves_no_work_file(services, copy):
    services.backups.restore(copy, NOW)

    assert account_names(services) == ["Banco"]
    assert work_files(services) == []


def test_a_copy_missing_a_table_is_refused_and_the_data_stays(services, copy):
    connection = sqlite3.connect(copy)
    connection.execute("DROP TABLE goals")
    connection.commit()
    connection.close()

    with pytest.raises(ValidationError, match="incompleta"):
        services.backups.restore(copy, NOW)

    assert account_names(services) == ["Cambiado"]
    assert work_files(services) == []


def test_a_copy_whose_rows_point_nowhere_is_refused(services, copy):
    connection = sqlite3.connect(copy)
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.execute("UPDATE transactions SET account_id = 999")
    connection.execute(
        "INSERT INTO transactions (account_id, type, amount_cents, occurred_on, category_id)"
        " SELECT 999, 'expense', 100, '2026-11-01', id FROM categories LIMIT 1"
    )
    connection.commit()
    connection.close()

    with pytest.raises(ValidationError, match="incompleta"):
        services.backups.restore(copy, NOW)

    assert account_names(services) == ["Cambiado"]


def test_a_full_disk_halfway_leaves_the_data_as_it_was(services, copy, monkeypatch):
    def full_disk(self, other):
        raise sqlite3.OperationalError("database or disk is full")

    monkeypatch.setattr(Database, "replace_with", full_disk)

    with pytest.raises(BackupError):
        services.backups.restore(copy, NOW)

    assert account_names(services) == ["Cambiado"]
    assert work_files(services) == []


def test_a_work_file_left_by_a_restore_cut_short_is_cleared(services, copy):
    folder = services.transactions._database.path.parent
    (folder / restore.WORK_NAME).write_bytes(b"half a copy")

    services.backups.restore(copy, NOW)

    assert account_names(services) == ["Banco"]
    assert work_files(services) == []


def test_an_older_copy_leaves_no_update_copy_behind(services, tmp_path):
    from nodus.database.database import load_packaged_migrations

    older = tmp_path / "older.db"
    migrations = sorted(load_packaged_migrations(), key=lambda m: m.version)
    Database.open(older, migrations[:-1]).close()

    services.backups.restore(older, NOW)

    work = services.transactions._database.path.parent / restore.WORK_NAME
    assert migration_backups(work) == []


class TestUndoAfterRestoring:
    """«Deshacer» belongs to the data before the copy: undoing it would write old changes
    over the restored data."""

    def test_ctrl_z_has_nothing_to_undo(self, services, pesos, copy):
        charge = services.recurring.create(charge_draft(services, pesos.id, ars("100")))
        services.recurring.skip(charge.id)

        services.backups.restore(copy, NOW)

        with pytest.raises(UndoError, match="No hay nada para deshacer"):
            services.undo.undo()

    def test_the_toast_still_on_screen_cannot_undo_either(self, services, pesos, copy):
        charge = services.recurring.create(charge_draft(services, pesos.id, ars("100")))
        services.recurring.skip(charge.id)
        offered = services.undo.last

        services.backups.restore(copy, NOW)

        with pytest.raises(UndoError, match="restaurar una copia"):
            services.undo.undo(offered)


def test_a_restored_copy_can_take_new_movements(services, pesos, copy):
    services.backups.restore(copy, NOW)

    services.transactions.create(expense_draft(services, pesos.id, ars("10")))
