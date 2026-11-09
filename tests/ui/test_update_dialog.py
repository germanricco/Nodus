import dataclasses
import hashlib
import threading

import pytest
from PySide6.QtWidgets import QDialog

from nodus.services.update_service import Installer, Release, UpdateService
from nodus.ui import browser, main_window
from nodus.ui.dialogs.update_dialog import UpdateDialog, megabytes

SETUP = b"setup program" * 50_000
RELEASE = Release(
    "9.0.0",
    "https://example.com/v9",
    "- Algo nuevo.",
    Installer("https://example.com/setup.exe", len(SETUP), hashlib.sha256(SETUP).hexdigest()),
)


def chunks(data: bytes, size: int = 64 * 1024):
    return [data[start : start + size] for start in range(0, len(data), size)]


@pytest.fixture
def launched() -> list[list[str]]:
    return []


def updates_with(tmp_path, launched, stream=None) -> UpdateService:
    return UpdateService(
        "1.2.0",
        stream=stream or (lambda _url: iter(chunks(SETUP))),
        downloads_dir=tmp_path / "updates",
        launch=launched.append,
    )


def open_dialog(qtbot, updates) -> UpdateDialog:
    dialog = UpdateDialog(updates, RELEASE)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.start()
    return dialog


def test_megabytes_are_written_like_windows_in_spanish():
    assert megabytes(24_578_342) == "23,4"
    assert megabytes(0) == "0,0"


def test_download_shows_progress_then_starts_the_installer(qtbot, tmp_path, launched):
    dialog = open_dialog(qtbot, updates_with(tmp_path, launched))

    qtbot.waitUntil(lambda: dialog.installing)

    assert dialog.progress_bar.value() == len(SETUP)
    assert dialog.detail_label.text() == f"{megabytes(len(SETUP))} de {megabytes(len(SETUP))} MB"
    assert launched[0][0] == str(tmp_path / "updates" / "Nodus-Setup-9.0.0.exe")
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_damaged_download_offers_the_release_page(qtbot, tmp_path, launched, monkeypatch):
    urls = []
    monkeypatch.setattr(
        browser.QDesktopServices, "openUrl", lambda url: urls.append(url.toString())
    )
    damaged = updates_with(tmp_path, launched, lambda _url: iter([b"not the installer"]))
    dialog = open_dialog(qtbot, damaged)

    qtbot.waitUntil(lambda: dialog.page_button.isVisible())

    assert "dañada" in dialog.detail_label.text()
    assert dialog.cancel_button.text() == "Cerrar"
    assert not dialog.installing and launched == []
    dialog.page_button.click()
    assert urls == ["https://example.com/v9"]


def test_cancel_stops_the_download_and_installs_nothing(qtbot, tmp_path, launched):
    first_chunk_sent = threading.Event()
    go_on = threading.Event()

    def slow(_url):
        for index, chunk in enumerate(chunks(SETUP)):
            if index == 1:
                first_chunk_sent.set()
                go_on.wait(5)
            yield chunk

    dialog = open_dialog(qtbot, updates_with(tmp_path, launched, slow))
    qtbot.waitUntil(first_chunk_sent.is_set)

    dialog.cancel_button.click()
    assert dialog.status_label.text() == "Cancelando…"
    go_on.set()
    qtbot.waitUntil(lambda: not dialog.isVisible())
    assert dialog.result() == QDialog.DialogCode.Rejected

    assert launched == []
    assert list((tmp_path / "updates").iterdir()) == []


class FakeUpdateDialog:
    """Stands in for the download, so the window's part is tested on its own."""

    def __init__(self, _updates, _release, parent=None) -> None:
        self.installing = True

    def exec(self) -> int:
        return QDialog.DialogCode.Accepted


def test_window_closes_nodus_once_the_installer_runs(
    window, services, tmp_path, launched, monkeypatch
):
    quit_calls = []
    monkeypatch.setattr(main_window.QApplication, "quit", lambda: quit_calls.append(True))
    monkeypatch.setattr(main_window, "UpdateDialog", FakeUpdateDialog)
    installable = dataclasses.replace(services, updates=updates_with(tmp_path, launched))
    monkeypatch.setattr(window, "_services", installable)

    window.start_update(RELEASE)

    assert quit_calls == [True]


def test_window_opens_the_page_when_it_cannot_install(window, monkeypatch):
    urls = []
    monkeypatch.setattr(
        browser.QDesktopServices, "openUrl", lambda url: urls.append(url.toString())
    )

    window.start_update(RELEASE)  # the tests run from the source code

    assert urls == ["https://example.com/v9"]
