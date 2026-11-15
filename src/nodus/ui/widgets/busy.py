"""A button that says it is working while what it started runs, so a second click
neither repeats it nor goes unanswered."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton

_IDLE_TEXT = "idle_text"


def start_busy(button: QPushButton, text: str) -> None:
    """Disables ``button`` and shows ``text`` («Actualizando…») until ``stop_busy``."""
    if button.property(_IDLE_TEXT) is None:
        button.setProperty(_IDLE_TEXT, button.text())
    button.setEnabled(False)
    button.setText(text)


def stop_busy(button: QPushButton) -> None:
    """Gives ``button`` back its text and its click."""
    idle = button.property(_IDLE_TEXT)
    if idle is not None:
        button.setText(idle)
        button.setProperty(_IDLE_TEXT, None)
    button.setEnabled(True)


def is_busy(button: QPushButton) -> bool:
    return button.property(_IDLE_TEXT) is not None


@contextmanager
def busy(button: QPushButton | None, text: str) -> Iterator[None]:
    """For work that runs on the interface thread, such as a copy: ``button`` says
    ``text`` and the pointer waits until it ends, however it ends."""
    if button is not None:
        start_busy(button, text)
        button.repaint()  # the thread is about to be taken: show it now
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()
        if button is not None:
            stop_busy(button)
