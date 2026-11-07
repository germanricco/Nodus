import sys

import pytest
from factories import FakeRegistry

from nodus.services.startup_service import StartupService, WindowsRunKey

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
