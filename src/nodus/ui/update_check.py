"""Runs the update check off the interface thread."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThreadPool, Signal

from nodus.services.update_service import UpdateService


class UpdateCheck(QObject):
    """Asks GitHub for a new version in the background, so a slow or missing connection
    never delays opening the window. ``found`` arrives on the interface thread."""

    found = Signal(object)  # Release

    def __init__(self, service: UpdateService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._service = service

    def start(self) -> None:
        QThreadPool.globalInstance().start(self._run)

    def _run(self) -> None:
        release = self._service.check()
        if release is not None:
            self.found.emit(release)
