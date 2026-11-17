"""Starting Nodus: what fails before the window is logged and told, never a silent exit."""

import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from factories import ars, services_for
from PySide6.QtWidgets import QDialog, QLineEdit

from nodus import app
from nodus.app import NEWER_DATA, OPEN_FAILED, UPDATE_FAILED, NodusApp
from nodus.config.paths import AppPaths
from nodus.database.database import (
    Database,
    DatabaseError,
    MigrationError,
    latest_schema_version,
)
from nodus.links import DOWNLOAD_URL
from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.ui import error_reporter
from nodus.ui.dialogs import user_error as user_error_module
from nodus.ui.dialogs.recovery_dialog import DAMAGED
from nodus.ui.dialogs.user_error import UnexpectedErrorDialog, UserErrorDialog
from nodus.ui.shell.single_instance import SingleInstance


@pytest.fixture
def nodus_app(qapp, tmp_path) -> NodusApp:
    """A ``NodusApp`` over ``tmp_path``, on the tests' QApplication: there can be one."""
    nodus = NodusApp.__new__(NodusApp)
    nodus._qt_app = qapp
    nodus._paths = AppPaths(tmp_path / "Nodus")
    nodus._smoke_test = None
    nodus._qt_texts = None
    return nodus


def log_text(nodus: NodusApp) -> str:
    return (nodus._paths.logs_dir / "nodus.log").read_text(encoding="utf-8")


def test_data_that_cannot_be_opened_is_told_and_logged(nodus_app, monkeypatch):
    errors = []

    def locked(path):
        raise DatabaseError(f"{path}: database is locked")

    monkeypatch.setattr(app.Database, "open", locked)
    monkeypatch.setattr(app, "user_error", lambda *args: errors.append(args))

    assert nodus_app.run() == 1
    assert errors[0][2] == OPEN_FAILED
    text = log_text(nodus_app)
    assert "The data could not be opened" in text
    assert "database is locked" in text
    assert str(nodus_app._paths.data_dir) not in text
    assert text.rstrip().endswith("Closed")


def test_a_failure_before_the_window_shows_the_error_dialog(nodus_app, monkeypatch):
    shown = []

    def broken(*_args):
        raise RuntimeError("could not start")

    monkeypatch.setattr(app.Services, "create", broken)
    monkeypatch.setattr(
        error_reporter.UnexpectedErrorDialog, "exec", lambda dialog: shown.append(dialog) or 0
    )

    assert nodus_app.run() == 1
    assert len(shown) == 1
    assert "RuntimeError: could not start" in log_text(nodus_app)


def test_the_log_starts_with_the_version_and_follows_the_data_folder(nodus_app, monkeypatch):
    monkeypatch.setattr(app.Database, "open", lambda path: (_ for _ in ()).throw(DatabaseError()))
    monkeypatch.setattr(app, "user_error", lambda *args: None)
    nodus_app.run()

    first_line = log_text(nodus_app).splitlines()[0]
    assert "Starting: Nodus " in first_line


class Opened:
    """What a run got to open, in place of the window and its event loop."""

    def __init__(self, nodus: NodusApp, monkeypatch) -> None:
        self.services = None
        self.accounts: list[str] = []  # read while the data is open
        self.dialogs: list[UserErrorDialog] = []
        self.answer = QDialog.DialogCode.Accepted

        def open_window(services):
            self.services = services
            self.accounts = [account.name for account in services.accounts.list_accounts()]
            nodus._window = MainWindowStandIn()

        def answer(dialog):
            self.dialogs.append(dialog)
            return self.answer

        monkeypatch.setattr(nodus, "_open_window", open_window)
        monkeypatch.setattr(nodus, "_qt_app", SimpleNamespace(exec=lambda: 0))
        monkeypatch.setattr(user_error_module.UserErrorDialog, "exec", answer)


class MainWindowStandIn:
    def __init__(self) -> None:
        self.brought_forward = 0

    def bring_to_front(self) -> None:
        self.brought_forward += 1


@pytest.fixture
def opened(nodus_app, monkeypatch) -> Opened:
    return Opened(nodus_app, monkeypatch)


def save_copy(paths: AppPaths, name: str, account: str) -> Path:
    """A copy in the backups folder holding one account called ``account``."""
    paths.backups_dir.mkdir(parents=True, exist_ok=True)
    database = Database.open(paths.backups_dir / name)
    services_for(database).accounts.create(account, AccountType.CASH, Currency.ARS, ars("0"))
    database.close()
    return paths.backups_dir / name


def damage(paths: AppPaths) -> bytes:
    paths.database_path.write_bytes(b"not a database" * 300)
    return paths.database_path.read_bytes()


def test_damaged_data_comes_back_from_the_newest_copy(nodus_app, opened):
    paths = nodus_app._paths
    paths.ensure_data_dir()
    old = save_copy(paths, "nodus-2026-11-15.db", "Vieja")
    os.utime(old, (1_000_000, 1_000_000))
    save_copy(paths, "nodus-2026-11-16.db", "Nueva")
    damaged_bytes = damage(paths)

    assert nodus_app.run() == 0
    assert opened.dialogs[0].what_label.text() == DAMAGED
    assert opened.accounts == ["Nueva"]
    aside = list(paths.data_dir.glob("nodus-dañado-*.db"))
    assert len(aside) == 1
    assert aside[0].read_bytes() == damaged_bytes


def test_declining_the_copy_leaves_the_damaged_data_untouched(nodus_app, opened):
    paths = nodus_app._paths
    paths.ensure_data_dir()
    save_copy(paths, "nodus-2026-11-16.db", "Nueva")
    damaged_bytes = damage(paths)
    opened.answer = QDialog.DialogCode.Rejected

    assert nodus_app.run() == 1
    assert paths.database_path.read_bytes() == damaged_bytes
    assert opened.services is None


def test_damaged_data_without_copies_says_where_to_put_one(nodus_app, opened):
    paths = nodus_app._paths
    paths.ensure_data_dir()
    damage(paths)

    assert nodus_app.run() == 1
    assert str(paths.backups_dir) in opened.dialogs[0].how_label.text()


def test_data_from_a_newer_nodus_offers_the_download(nodus_app, opened, monkeypatch):
    paths = nodus_app._paths
    paths.ensure_data_dir()
    Database.open(paths.database_path).close()
    raw = sqlite3.connect(paths.database_path)
    raw.execute(f"PRAGMA user_version = {latest_schema_version() + 1}")
    raw.close()
    before = paths.database_path.read_bytes()
    urls = []
    monkeypatch.setattr(app, "open_url", urls.append)

    assert nodus_app.run() == 1
    assert opened.dialogs[0].what_label.text() == NEWER_DATA
    assert urls == [DOWNLOAD_URL]
    assert paths.database_path.read_bytes() == before


def test_a_failed_update_of_the_data_offers_the_report(nodus_app, opened, monkeypatch):
    def broken(path):
        raise MigrationError("migration 13 failed")

    monkeypatch.setattr(app.Database, "open", broken)

    assert nodus_app.run() == 1
    assert isinstance(opened.dialogs[0], UnexpectedErrorDialog)
    assert opened.dialogs[0].what_label.text() == UPDATE_FAILED


def test_opening_nodus_again_brings_the_open_one_forward(nodus_app, opened, qtbot):
    nodus_app._paths.ensure_data_dir()
    first = SingleInstance(nodus_app._paths.data_dir)
    assert first.acquire()
    try:
        with qtbot.waitSignal(first.show_requested, timeout=2000):
            assert nodus_app.run() == 0
    finally:
        first.release()
    assert opened.services is None
    assert not (nodus_app._paths.logs_dir / "nodus.log").exists()


def test_the_open_one_comes_forward_when_asked(nodus_app, opened, qtbot):
    nodus_app._qt_app = SimpleNamespace(exec=lambda: ask_again(nodus_app, qtbot))

    assert nodus_app.run() == 0
    assert nodus_app._window.brought_forward == 1


def ask_again(nodus: NodusApp, qtbot) -> int:
    """Opens Nodus a second time while the first is running, as the user would."""
    SingleInstance(nodus._paths.data_dir).ask_first_to_show()
    qtbot.waitUntil(lambda: nodus._window.brought_forward == 1)
    return 0


def test_the_menus_of_the_text_fields_speak_spanish(qapp):
    """Qt names those itself, in English unless its Spanish texts are loaded."""
    translator = app.spanish_qt_texts(qapp)
    try:
        field = QLineEdit()
        menu = field.createStandardContextMenu()
        texts = [action.text().split("\t")[0].replace("&", "") for action in menu.actions()]
    finally:
        qapp.removeTranslator(translator)

    assert "Copiar" in texts and "Pegar" in texts


def test_the_installer_keeps_the_spanish_texts():
    """The installer leaves out Qt's translations (45 MB) but that one."""
    spec = (Path(__file__).parents[1] / "packaging" / "nodus.spec").read_text(encoding="utf-8")

    assert f"PySide6/translations/{app.QT_TEXTS}.qm" in spec
