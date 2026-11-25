"""Nodus: local-first personal finance desktop application."""

import os
import sys

__version__ = "1.12.1"

# The program's name: the window, the data folder, the registry and the installer use it.
APP_NAME = "Nodus"
# How Nodus introduces itself to the services it asks for rates and updates.
USER_AGENT = f"{APP_NAME}/{__version__}"


def is_installed() -> bool:
    """Whether this is the installed program (on Windows) or the AppImage (on Linux), not
    Python running the source. Only these can update themselves or open at sign-in."""
    return getattr(sys, "frozen", False) and (sys.platform == "win32" or "APPIMAGE" in os.environ)


def program_path() -> str:
    """The file that opens this Nodus. An AppImage runs from a folder it mounts anew each
    time, so the file to open again is the AppImage itself, which it names in ``APPIMAGE``."""
    return os.environ.get("APPIMAGE") or sys.executable


# How Windows tells Nodus apart from other programs on the taskbar. The running process
# and the installer's shortcuts must carry the same one: a pinned window whose ID no
# shortcut declares shows a blank icon. Fixed forever, or existing pins stop matching.
APP_USER_MODEL_ID = "GermanRicco.Nodus"
# The same on Linux: the name of the program's ``.desktop`` file (packaging/nodus.desktop,
# in the AppImage), which Wayland desktops match the window to for its icon and name.
DESKTOP_FILE_ID = "nodus"
