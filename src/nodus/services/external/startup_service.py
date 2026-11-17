"""Opening Nodus when Windows starts, through the user's Run key in the registry."""

from __future__ import annotations

import sys
from typing import Protocol

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Nodus"


class StartupRegistry(Protocol):
    """Where the command that opens Nodus at sign-in is kept."""

    def read(self) -> str | None: ...

    def write(self, command: str) -> None: ...

    def delete(self) -> None: ...


class WindowsRunKey:
    """The ``Nodus`` value of ``HKCU\\...\\Run``: Windows runs it when the user signs in.

    Per user, like the installer, so it needs no administrator rights. ``key`` can be
    replaced so tests use a throwaway key instead of the real one.
    """

    def __init__(self, key: str = RUN_KEY) -> None:
        self._key = key

    def read(self) -> str | None:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._key) as key:
                value, _kind = winreg.QueryValueEx(key, VALUE_NAME)
        except OSError:
            return None
        return str(value)

    def write(self, command: str) -> None:
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self._key) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)

    def delete(self) -> None:
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self._key, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            pass


class StartupService:
    """Turns opening at sign-in on and off.

    Only the installed program offers it: run from the source code, the executable is
    Python itself, and registering it would open a bare interpreter at every sign-in.
    The state lives in the registry, not in the data file, because it belongs to the
    computer: copying the data to another PC does not carry it along.
    """

    def __init__(self, registry: StartupRegistry | None, executable: str) -> None:
        self._registry = registry
        self._command = f'"{executable}"'

    @classmethod
    def for_this_program(cls) -> StartupService:
        """Available only when running as the installed program on Windows."""
        installed = getattr(sys, "frozen", False) and sys.platform == "win32"
        return cls(WindowsRunKey() if installed else None, sys.executable)

    def is_available(self) -> bool:
        return self._registry is not None

    def is_enabled(self) -> bool:
        return self._registry is not None and self._registry.read() is not None

    def set_enabled(self, enabled: bool) -> None:
        if self._registry is None:
            raise RuntimeError("Opening at sign-in is only available in the installed program")
        if enabled:
            self._registry.write(self._command)
        else:
            self._registry.delete()

    def repair(self) -> None:
        """Points an existing entry at this executable, in case Nodus was reinstalled in
        another folder; without an entry, nothing changes."""
        if self.is_enabled() and self._registry.read() != self._command:
            self._registry.write(self._command)
