import shutil
import sys
from pathlib import Path

import pytest

from nodus.services.external.desktop_entry import DesktopEntry, data_home

PACKAGING = Path(__file__).parents[3] / "packaging"


@pytest.fixture
def app_dir(tmp_path) -> Path:
    """The folder an AppImage mounts, with the same .desktop file and icon the build puts."""
    folder = tmp_path / "mount"
    folder.mkdir()
    shutil.copy(PACKAGING / "nodus.desktop", folder)
    shutil.copy(PACKAGING / "nodus.png", folder)
    return folder


def test_the_menu_entry_opens_this_appimage(tmp_path, app_dir):
    appimage = tmp_path / "Mis programas" / "Nodus-1.11.0-x86_64.AppImage"
    entry = DesktopEntry(appimage, app_dir, tmp_path / "share")

    entry.install()

    lines = entry.desktop_file.read_text(encoding="utf-8").splitlines()
    assert f'Exec="{appimage}"' in lines
    assert f"TryExec={appimage}" in lines  # deleted, the desktop hides the entry
    assert "Icon=nodus" in lines and "Name=Nodus" in lines
    assert entry.icon_file.read_bytes() == (app_dir / "nodus.png").read_bytes()
    assert entry.icon_file.parts[-4:] == ("hicolor", "256x256", "apps", "nodus.png")


def test_a_moved_appimage_points_the_entry_at_its_new_place(tmp_path, app_dir):
    home = tmp_path / "share"
    DesktopEntry(tmp_path / "Descargas" / "Nodus.AppImage", app_dir, home).install()
    moved = DesktopEntry(tmp_path / "Programas" / "Nodus.AppImage", app_dir, home)

    moved.install()

    text = moved.desktop_file.read_text(encoding="utf-8")
    assert "Programas" in text and "Descargas" not in text
    assert text.count("Exec=") == 2  # Exec and TryExec, once each


def test_an_unchanged_entry_is_not_written_again(tmp_path, app_dir):
    entry = DesktopEntry(tmp_path / "Nodus.AppImage", app_dir, tmp_path / "share")
    entry.install()
    written = entry.desktop_file.stat().st_mtime_ns, entry.icon_file.stat().st_mtime_ns

    entry.install()

    assert (entry.desktop_file.stat().st_mtime_ns, entry.icon_file.stat().st_mtime_ns) == written


def test_a_folder_it_cannot_write_does_not_stop_nodus(tmp_path, app_dir, caplog):
    home = tmp_path / "share"
    home.write_text("a file where the folder should be", encoding="utf-8")

    DesktopEntry(tmp_path / "Nodus.AppImage", app_dir, home).install()

    assert "desktop entry was not installed" in caplog.text


def test_only_the_appimage_has_one(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("APPDIR", str(tmp_path))
    monkeypatch.delenv("APPIMAGE", raising=False)
    assert DesktopEntry.for_this_program() is None  # the source code, or a frozen folder

    monkeypatch.setenv("APPIMAGE", str(tmp_path / "Nodus.AppImage"))
    assert DesktopEntry.for_this_program() is not None


def test_the_data_folder_follows_xdg():
    assert data_home({"XDG_DATA_HOME": "/datos"}) == Path("/datos")
    assert data_home({}) == Path.home() / ".local" / "share"
