import sys
from pathlib import Path

import pytest
from factories import FakeRegistry

from nodus.services.external.startup_service import (
    StartupService,
    WindowsRunKey,
    XdgAutostart,
    autostart_folder,
)

# A throwaway key, so the tests never touch the real Run key.
TEST_PARENT_KEY = r"Software\NodusTests"
TEST_KEY = TEST_PARENT_KEY + r"\Run"

EXECUTABLE = r"C:\Users\Ana\AppData\Local\Programs\Nodus\Nodus.exe"


def test_turning_it_on_registers_the_quoted_executable():
    registry = FakeRegistry()
    startup = StartupService(registry, EXECUTABLE)
    assert startup.is_available() and not startup.is_enabled()

    startup.set_enabled(True)

    assert registry.value == f'"{EXECUTABLE}"'
    assert startup.is_enabled()

    startup.set_enabled(False)

    assert registry.value is None


def test_from_the_source_code_it_is_not_offered():
    startup = StartupService(None, "python.exe")

    assert not startup.is_available() and not startup.is_enabled()
    with pytest.raises(RuntimeError):
        startup.set_enabled(True)


def test_the_tests_never_touch_the_real_registry(services):
    assert not services.startup.is_available()


def test_repair_follows_a_program_moved_to_another_folder():
    registry = FakeRegistry(r'"D:\Viejo\Nodus.exe"')

    StartupService(registry, EXECUTABLE).repair()

    assert registry.value == f'"{EXECUTABLE}"'


def test_repair_never_turns_it_on():
    registry = FakeRegistry()

    StartupService(registry, EXECUTABLE).repair()

    assert registry.value is None


@pytest.mark.skipif(sys.platform != "win32", reason="the registry exists only on Windows")
def test_the_windows_run_key_reads_writes_and_deletes():
    import winreg

    registry = WindowsRunKey(TEST_KEY)
    try:
        assert registry.read() is None
        registry.write(f'"{EXECUTABLE}"')
        assert registry.read() == f'"{EXECUTABLE}"'
        registry.delete()
        assert registry.read() is None
        registry.delete()  # deleting twice is harmless
    finally:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, TEST_KEY)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, TEST_PARENT_KEY)


APPIMAGE = "/home/ana/Aplicaciones/Nodus-1.11.0-x86_64.AppImage"


def as_appimage(monkeypatch) -> None:
    """Runs the test as the AppImage on Linux: frozen, from a mounted folder."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "executable", "/tmp/.mount_NodusX/usr/bin/nodus")
    monkeypatch.setenv("APPIMAGE", APPIMAGE)


def test_the_linux_autostart_entry_reads_writes_and_deletes(tmp_path):
    registry = XdgAutostart(tmp_path)
    assert registry.read() is None

    registry.write(f'"{APPIMAGE}"')

    entry = (tmp_path / "nodus.desktop").read_text(encoding="utf-8").splitlines()
    assert entry[0] == "[Desktop Entry]" and f'Exec="{APPIMAGE}"' in entry
    assert registry.read() == f'"{APPIMAGE}"'
    registry.delete()
    assert registry.read() is None
    registry.delete()  # deleting twice is harmless


def test_the_autostart_folder_follows_xdg_config_home():
    folder = autostart_folder({"XDG_CONFIG_HOME": "/home/ana/.cfg"})
    assert folder == Path("/home/ana/.cfg/autostart")
    assert autostart_folder({}) == Path.home() / ".config" / "autostart"


def test_the_appimage_registers_itself_not_the_folder_it_runs_from(monkeypatch, tmp_path):
    as_appimage(monkeypatch)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    startup = StartupService.for_this_program()
    startup.set_enabled(True)

    assert startup.is_available()
    assert XdgAutostart(tmp_path / "autostart").read() == f'"{APPIMAGE}"'


def test_a_frozen_program_on_linux_outside_an_appimage_is_not_installed(monkeypatch):
    as_appimage(monkeypatch)
    monkeypatch.delenv("APPIMAGE")

    assert not StartupService.for_this_program().is_available()
