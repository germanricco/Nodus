"""Asking Nodus to close and open again, to apply what only applies on start."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

# The exit code that tells ``NodusApp`` to open Nodus again once it has closed.
RESTART_EXIT_CODE = 75


def restart() -> None:
    """Ends the event loop asking for a restart; ``NodusApp`` reopens Nodus after it
    has released the data, so the new one can take it."""
    QApplication.exit(RESTART_EXIT_CODE)
