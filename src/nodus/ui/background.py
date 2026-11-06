"""Runs slow work, like asking an online source, off the interface thread."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QThreadPool, Signal


class BackgroundCall(QObject):
    """Calls ``function`` on a worker thread and delivers its result with ``done``.

    ``done`` arrives on the interface thread, so its slots can touch widgets. Keeps a slow
    or missing connection from ever delaying the window.
    """

    done = Signal(object)

    def __init__(self, function: Callable[[], object], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._function = function

    def start(self) -> None:
        QThreadPool.globalInstance().start(self._run)

    def _run(self) -> None:
        self.done.emit(self._function())
