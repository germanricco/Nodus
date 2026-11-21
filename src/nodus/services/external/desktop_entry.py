"""Nodus in the desktop's menu and dock on Linux, which an AppImage does not get on its own.

The desktop finds a program's icon and name in a ``.desktop`` file it has installed, so
a window whose file it lacks shows a generic icon. Each time it opens, the AppImage puts
its own ``.desktop`` file and icon in the user's folders, pointing at the AppImage where
it is now. ``TryExec`` names that file: if the user deletes it, the desktop hides the
entry.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Mapping
from pathlib import Path

from nodus import DESKTOP_FILE_ID, is_installed
from nodus.services.external.startup_service import EXEC_KEY, program_command

ICON_SIZE = "256x256"  # the size of packaging/nodus.png
TRY_EXEC_KEY = "TryExec="

logger = logging.getLogger(__name__)


def data_home(environ: Mapping[str, str] = os.environ) -> Path:
    """``$XDG_DATA_HOME``, by default ``~/.local/share``."""
    return Path(environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share"))


class DesktopEntry:
    """The ``.desktop`` file and icon of one AppImage, copied from the folder it mounts
    (``app_dir``) into ``home``, the user's data folder; tests give throwaway ones."""

    def __init__(self, appimage: Path, app_dir: Path, home: Path | None = None) -> None:
        self._appimage = appimage
        self._app_dir = app_dir
        home = home or data_home()
        self.desktop_file = home / "applications" / f"{DESKTOP_FILE_ID}.desktop"
        self.icon_file = home / "icons" / "hicolor" / ICON_SIZE / "apps" / f"{DESKTOP_FILE_ID}.png"

    @classmethod
    def for_this_program(cls) -> DesktopEntry | None:
        """Only for the AppImage: from the source code, or on Windows, there is none."""
        appimage, app_dir = os.environ.get("APPIMAGE"), os.environ.get("APPDIR")
        if sys.platform != "linux" or not is_installed() or not appimage or not app_dir:
            return None
        return cls(Path(appimage), Path(app_dir))

    def install(self) -> None:
        """Writes both files when they are missing or name another place. A folder it
        cannot write is only logged: Nodus opens all the same, with a generic icon."""
        try:
            self._write_if_changed(self.desktop_file, self._desktop_text().encode("utf-8"))
            icon = self._app_dir / f"{DESKTOP_FILE_ID}.png"
            self._write_if_changed(self.icon_file, icon.read_bytes())
        except OSError as error:
            logger.warning("The desktop entry was not installed: %s", type(error).__name__)

    def _desktop_text(self) -> str:
        """The AppImage's own ``.desktop`` file, opening this AppImage."""
        source = self._app_dir / f"{DESKTOP_FILE_ID}.desktop"
        lines = []
        for line in source.read_text(encoding="utf-8").splitlines():
            if line.startswith(EXEC_KEY):
                lines.append(EXEC_KEY + program_command(str(self._appimage)))
                lines.append(TRY_EXEC_KEY + str(self._appimage))
            elif not line.startswith(TRY_EXEC_KEY):
                lines.append(line)
        return "\n".join([*lines, ""])

    @staticmethod
    def _write_if_changed(path: Path, content: bytes) -> None:
        # Unchanged files stay as they are, so the desktop does not reload its menu at
        # every opening.
        if path.is_file() and path.read_bytes() == content:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
