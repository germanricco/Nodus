"""An error nothing caught reaches the log and a dialog, once, from any thread."""

import logging
import sys
import threading
from urllib.parse import parse_qs, urlparse

import pytest
from PySide6.QtCore import QTimer

from nodus.config.logs import RunLog
from nodus.ui import browser, error_reporter
from nodus.ui.dialogs.user_error import UNEXPECTED_WHAT, UnexpectedErrorDialog
from nodus.ui.error_reporter import ErrorReporter


def raised(message: str = "broken") -> RuntimeError:
    try:
        raise RuntimeError(message)
    except RuntimeError as error:
        return error


@pytest.fixture
def shown(monkeypatch) -> list[BaseException]:
    """The errors a dialog opened for, without waiting on the modal dialog."""
    errors: list[BaseException] = []
    monkeypatch.setattr(
        error_reporter.UnexpectedErrorDialog, "exec", lambda dialog: errors.append(dialog) or 0
    )
    return errors


@pytest.fixture
def reporter(qapp, tmp_path):
    log = RunLog(tmp_path / "logs")
    log.start()
    reporter = ErrorReporter(tmp_path / "logs")
    reporter.install()
    yield reporter
    reporter.uninstall()
    log.stop()


def log_text(tmp_path) -> str:
    return (tmp_path / "logs" / "nodus.log").read_text(encoding="utf-8")


@pytest.mark.qt_no_exception_capture
def test_an_error_in_a_slot_is_logged_and_shown(reporter, shown, qtbot, tmp_path):
    def broken_slot():
        raise RuntimeError("broken slot")

    QTimer.singleShot(0, broken_slot)
    qtbot.waitUntil(lambda: len(shown) == 1)

    assert "RuntimeError: broken slot" in log_text(tmp_path)
    assert "in broken_slot" in log_text(tmp_path)


def test_an_error_in_another_thread_is_shown_from_the_window_thread(
    reporter, shown, qtbot, tmp_path
):
    def broken_work():
        raise ValueError("broken work")

    worker = threading.Thread(target=broken_work)
    worker.start()
    worker.join()
    qtbot.waitUntil(lambda: len(shown) == 1)

    assert "ValueError: broken work" in log_text(tmp_path)


def test_the_same_error_opens_one_dialog_and_is_logged_each_time(reporter, shown, qtbot, tmp_path):
    for _ in range(3):
        sys.excepthook(RuntimeError, (error := raised()), error.__traceback__)
        qtbot.wait(10)

    assert len(shown) == 1
    assert log_text(tmp_path).count("RuntimeError: broken") == 3


def test_an_error_while_a_dialog_is_open_is_only_logged(reporter, monkeypatch, qtbot):
    opened = []

    def exec_with_another_error(dialog):
        opened.append(dialog)
        reporter.show(ValueError("while open"))
        return 0

    monkeypatch.setattr(error_reporter.UnexpectedErrorDialog, "exec", exec_with_another_error)
    reporter.show(raised())

    assert len(opened) == 1


def test_uninstall_puts_back_the_previous_hooks(qapp, tmp_path):
    before = (sys.excepthook, threading.excepthook)
    reporter = ErrorReporter(tmp_path)
    reporter.install()
    assert sys.excepthook != before[0]
    reporter.uninstall()

    assert (sys.excepthook, threading.excepthook) == before


def test_the_dialog_offers_the_report_and_the_log(qtbot, monkeypatch, tmp_path):
    opened = []
    monkeypatch.setattr(browser.QDesktopServices, "openUrl", lambda url: opened.append(url))
    dialog = UnexpectedErrorDialog(raised("could not save «Banco»"), tmp_path / "logs")
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.what_label.text() == UNEXPECTED_WHAT
    assert dialog.close_button.isDefault()
    dialog.report_button.click()
    query = parse_qs(urlparse(opened[0].toString()).query)
    assert query["entry.1417373821"] == ["Algo no funciona"]
    assert "RuntimeError: could not save «…»" in query["entry.1232171367"][0]
    dialog.logs_button.click()
    assert opened[1].toLocalFile().endswith("logs")
    assert (tmp_path / "logs").is_dir()


def test_the_dialog_detail_is_the_scrubbed_traceback(qtbot, tmp_path):
    dialog = UnexpectedErrorDialog(raised("amount 98765"), tmp_path)
    qtbot.addWidget(dialog)

    assert "RuntimeError: amount …" in dialog.detail.text.toPlainText()
    assert "in raised" in dialog.detail.text.toPlainText()


def test_logging_stays_quiet_without_a_run_log():
    assert logging.getLogger("nodus").handlers == []
