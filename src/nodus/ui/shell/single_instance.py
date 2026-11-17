"""One Nodus at a time over the same data.

Two windows over one file would each keep its own picture of the data, and the second
one's writes would undo what the first one showed. Opening Nodus again instead brings
the open window to the front, which is what the user wanted anyway.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

LOCK_FILENAME = "nodus.lock"
ANSWER_TIMEOUT = 1000  # milliseconds the open Nodus has to answer


def server_name(data_dir: Path) -> str:
    """The name the open Nodus listens on: one per data folder, so a test copy of the
    data (``NODUS_DATA_DIR``) opens beside the real one."""
    folder = str(data_dir.resolve()).casefold()
    return "Nodus-" + hashlib.sha256(folder.encode("utf-8")).hexdigest()[:16]


class SingleInstance(QObject):
    """Holds a lock file in the data folder while Nodus runs. The first Nodus takes it
    and listens; a later one finds it taken and asks the first, through a local socket,
    to come to the front.

    The lock dies with its process, so a Nodus that crashed never keeps the next one
    from opening.
    """

    show_requested = Signal()

    def __init__(self, data_dir: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._lock = QLockFile(str(data_dir / LOCK_FILENAME))
        self._lock.setStaleLockTime(0)  # stale only when its process is gone
        self._name = server_name(data_dir)
        self._server: QLocalServer | None = None

    def acquire(self) -> bool:
        """True if this is the only Nodus over the data; it then listens for others."""
        if not self._lock.tryLock(0):
            return False
        QLocalServer.removeServer(self._name)  # left behind by a Nodus that crashed
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_connection)
        self._server.listen(self._name)
        return True

    def ask_first_to_show(self) -> bool:
        """Asks the Nodus that holds the lock to come to the front; False if it does not
        answer, as when it is stuck. Connecting is the whole request."""
        socket = QLocalSocket()
        socket.connectToServer(self._name)
        connected = socket.waitForConnected(ANSWER_TIMEOUT)
        socket.abort()
        return connected

    def release(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None
        self._lock.unlock()

    def _on_connection(self) -> None:
        assert self._server is not None
        while (socket := self._server.nextPendingConnection()) is not None:
            socket.disconnected.connect(socket.deleteLater)
            socket.disconnectFromServer()
            self.show_requested.emit()
