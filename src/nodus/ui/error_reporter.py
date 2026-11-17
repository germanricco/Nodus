"""Catches the errors nothing else caught, anywhere in Nodus, so none fails in silence."""

from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path
from types import TracebackType

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QApplication

from nodus.config.logs import frames
from nodus.ui.dialogs.user_error import UnexpectedErrorDialog

logger = logging.getLogger(__name__)


def error_key(error: BaseException) -> tuple[str, str, int]:
    """What tells one error from another: its kind and the step where it was raised."""
    steps = frames(error)
    last = steps[-1] if steps else None
    return type(error).__name__, last.path if last else "", last.line if last else 0


class ErrorReporter(QObject):
    """Installed by ``NodusApp`` for the whole run. An error that reaches the top, in the
    window's thread or in another, is written to the log with its traceback and shown
    with ``UnexpectedErrorDialog``, from the window's thread.

    One dialog at a time, and each distinct error once: an error raised while painting
    comes back on every paint, and a dialog each time would leave Nodus unusable. The
    repeats still reach the log.
    """

    _caught = Signal(object)  # BaseException, from any thread

    def __init__(self, logs_dir: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._logs_dir = logs_dir
        self._shown: set[tuple[str, str, int]] = set()
        self._showing = False
        self._previous: tuple[object, object] | None = None
        # Queued even from the window's thread: the dialog then never opens in the middle
        # of what failed, such as a paint.
        self._caught.connect(self.show, Qt.ConnectionType.QueuedConnection)

    def install(self) -> None:
        self._previous = (sys.excepthook, threading.excepthook)
        sys.excepthook = self._on_error
        threading.excepthook = self._on_thread_error

    def uninstall(self) -> None:
        if self._previous is not None:
            sys.excepthook, threading.excepthook = self._previous  # type: ignore[assignment]
            self._previous = None

    def report(self, error: BaseException) -> None:
        """Logs ``error`` and shows it as soon as the window's thread is free."""
        logger.error("Unexpected error", exc_info=error)
        self._caught.emit(error)

    def show(self, error: BaseException) -> None:
        """Shows ``error`` now, unless a dialog is open or it was shown already."""
        key = error_key(error)
        if self._showing or key in self._shown:
            return
        self._shown.add(key)
        self._showing = True
        try:
            UnexpectedErrorDialog(error, self._logs_dir, QApplication.activeWindow()).exec()
        finally:
            self._showing = False

    def _on_error(
        self, kind: type[BaseException], error: BaseException, trace: TracebackType | None
    ) -> None:
        if issubclass(kind, KeyboardInterrupt):
            sys.__excepthook__(kind, error, trace)
            return
        self.report(error if error.__traceback__ else error.with_traceback(trace))

    def _on_thread_error(self, args: threading.ExceptHookArgs) -> None:
        if args.exc_value is None or issubclass(args.exc_type, SystemExit):
            return
        self.report(args.exc_value)
