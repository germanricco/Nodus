"""Nodus: local-first personal finance desktop application."""

import sys

__version__ = "1.9.0"

# The program's name: the window, the data folder, the registry and the installer use it.
APP_NAME = "Nodus"
# How Nodus introduces itself to the services it asks for rates and updates.
USER_AGENT = f"{APP_NAME}/{__version__}"


def is_installed() -> bool:
    """Whether this is the installed program on Windows, not Python running the source.
    Only the installed program can update itself or open at sign-in."""
    return getattr(sys, "frozen", False) and sys.platform == "win32"


# How Windows tells Nodus apart from other programs on the taskbar. The running process
# and the installer's shortcuts must carry the same one: a pinned window whose ID no
# shortcut declares shows a blank icon. Fixed forever, or existing pins stop matching.
APP_USER_MODEL_ID = "GermanRicco.Nodus"
