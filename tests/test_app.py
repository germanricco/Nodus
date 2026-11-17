"""Starting Nodus: what fails before the window is logged and told, never a silent exit."""

import pytest

from nodus import app
from nodus.app import OPEN_FAILED, NodusApp
from nodus.config.paths import AppPaths
from nodus.database.database import DatabaseError
from nodus.ui import error_reporter


@pytest.fixture
def nodus_app(qapp, tmp_path) -> NodusApp:
    """A ``NodusApp`` over ``tmp_path``, on the tests' QApplication: there can be one."""
    nodus = NodusApp.__new__(NodusApp)
    nodus._qt_app = qapp
    nodus._paths = AppPaths(tmp_path / "Nodus")
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
