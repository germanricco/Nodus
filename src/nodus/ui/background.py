"""Runs slow work, like asking an online source, off the interface thread."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QThreadPool, Signal

logger = logging.getLogger(__name__)


class BackgroundCall(QObject):
    """Calls ``function`` on a worker thread and delivers its result with ``done``, or
    ``failed`` if it raised: one of the two always comes, so whatever waits for it (a
    busy button) never waits forever.

    Both arrive on the interface thread, so their slots can touch widgets. Keeps a slow
    or missing connection from ever delaying the window.

    Services answer a missing connection themselves, so an error that reaches here is
    one nobody expected: no screen shows the system's text, so it goes to the log, with
    its traceback.
    """

    done = Signal(object)
    failed = Signal()

    def __init__(self, function: Callable[[], object], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._function = function

    def start(self) -> None:
        QThreadPool.globalInstance().start(self._run)

    def _run(self) -> None:
        try:
            result = self._function()
        except Exception as error:  # noqa: BLE001 - any failure must reach the interface
            logger.error("Work in the background failed", exc_info=error)
            self.failed.emit()
            return
        self.done.emit(result)
