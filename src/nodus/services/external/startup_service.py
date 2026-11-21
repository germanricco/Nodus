"""Opening Nodus when the user signs in: through the Run key of the registry on Windows,
and an autostart entry of the desktop on Linux."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from nodus import APP_NAME, is_installed, program_path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = APP_NAME
AUTOSTART_FILE = "nodus.desktop"
EXEC_KEY = "Exec="


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


def program_command(executable: str) -> str:
    """The command that opens ``executable``, quoted so a path with spaces stays whole:
    for the Run key and for the ``Exec`` line of a ``.desktop`` file alike."""
    return f'"{executable}"'


def autostart_folder(environ: Mapping[str, str] = os.environ) -> Path:
    """``$XDG_CONFIG_HOME/autostart``, by default ``~/.config/autostart``."""
    config = environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(config) / "autostart"


class XdgAutostart:
    """``nodus.desktop`` in the autostart folder: GNOME, KDE, XFCE and the other Linux
    desktops open what its ``Exec`` line names when the user signs in. Per user, like the
    Run key; ``folder`` can be replaced so tests use a throwaway one."""

    def __init__(self, folder: Path | None = None) -> None:
        self._file = (folder or autostart_folder()) / AUTOSTART_FILE

    def read(self) -> str | None:
        try:
            lines = self._file.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return None
        commands = [line.removeprefix(EXEC_KEY) for line in lines if line.startswith(EXEC_KEY)]
        return commands[0] if commands else None

    def write(self, command: str) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        entry = ["[Desktop Entry]", "Type=Application", f"Name={APP_NAME}", EXEC_KEY + command]
        self._file.write_text("\n".join([*entry, "Terminal=false", ""]), encoding="utf-8")

    def delete(self) -> None:
        self._file.unlink(missing_ok=True)


class StartupService:
    """Turns opening at sign-in on and off.

    Only the installed program offers it: run from the source code, the executable is
    Python itself, and registering it would open a bare interpreter at every sign-in.
    The state lives in the system (the registry or the autostart folder), not in the
    data file, because it belongs to the
    computer: copying the data to another PC does not carry it along.
    """

    def __init__(self, registry: StartupRegistry | None, executable: str) -> None:
        self._registry = registry
        self._command = program_command(executable)

    @classmethod
    def for_this_program(cls) -> StartupService:
        """Available only when running as the installed program or the AppImage."""
        if not is_installed():
            return cls(None, program_path())
        registry = WindowsRunKey() if sys.platform == "win32" else XdgAutostart()
        return cls(registry, program_path())

    def is_available(self) -> bool:
        """Only the installed program can open at sign-in: a copy run from the code has no
        fixed place to start from."""
        return self._registry is not None

    def is_enabled(self) -> bool:
        """Whether the system opens Nodus when the user signs in."""
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
