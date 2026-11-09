"""Downloads a new version with its progress in view, then hands over to its installer."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nodus.services.errors import UpdateError
from nodus.services.update_service import Release, UpdateService
from nodus.ui.background import BackgroundCall
from nodus.ui.browser import open_url
from nodus.ui.widgets.style import set_style_name

MEBIBYTE = 1024 * 1024  # what Windows calls a MB


def megabytes(size: int) -> str:
    """``size`` bytes the way Windows shows them, in Spanish: "23,4"."""
    return f"{size / MEBIBYTE:.1f}".replace(".", ",")


class UpdateDialog(QDialog):
    """Shows the download of ``release`` and, once it arrived intact, starts its installer.

    ``installing`` turns true when the installer is running: the caller must then close
    Nodus so its files can be replaced. A failure offers the release page instead.
    """

    progressed = Signal(int)

    def __init__(
        self, updates: UpdateService, release: Release, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._updates = updates
        self._release = release
        self._cancel_requested = False
        self._downloading = False
        self.installing = False
        self.setWindowTitle("Actualizar Nodus")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        self.status_label = QLabel(f"Descargando Nodus {release.version}…")
        self.status_label.setObjectName("DialogTitle")
        layout.addWidget(self.status_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)
        self.detail_label = QLabel()
        self.detail_label.setObjectName("FieldHint")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.page_button = QPushButton("Abrir GitHub")
        self.page_button.setObjectName("SecondaryButton")
        self.page_button.clicked.connect(self._open_page)
        self.page_button.hide()
        buttons.addWidget(self.page_button)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setObjectName("SecondaryButton")
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)

        installer = release.installer
        self._total = installer.size if installer is not None else 0
        self.progress_bar.setRange(0, self._total)
        self.progressed.connect(self._show_progress)
        self._show_progress(0)

    def start(self) -> None:
        """Begins the download in the background; ``exec`` calls it, tests may call it."""
        self._downloading = True
        self._download = BackgroundCall(self._fetch, parent=self)
        self._download.done.connect(self._finish)
        self._download.start()

    def exec(self) -> int:
        self.start()
        return super().exec()

    def reject(self) -> None:
        """Closing while downloading cancels it; the dialog closes once it has stopped."""
        if not self._downloading:
            super().reject()
            return
        self._cancel_requested = True
        self.cancel_button.setEnabled(False)
        self.status_label.setText("Cancelando…")

    def _fetch(self) -> Path | UpdateError | None:
        """Runs on a worker thread; errors come back as values for the interface thread."""
        try:
            return self._updates.download(
                self._release, self.progressed.emit, lambda: self._cancel_requested
            )
        except UpdateError as error:
            return error

    def _show_progress(self, received: int) -> None:
        self.progress_bar.setValue(received)
        self.detail_label.setText(f"{megabytes(received)} de {megabytes(self._total)} MB")

    def _finish(self, result: Path | UpdateError | None) -> None:
        self._downloading = False
        if result is None:
            super().reject()
        elif isinstance(result, UpdateError):
            self._show_error(result)
        else:
            self._install(result)

    def _install(self, installer: Path) -> None:
        try:
            self._updates.install(installer)
        except UpdateError as error:
            self._show_error(error)
            return
        self.installing = True
        self.accept()

    def _show_error(self, error: UpdateError) -> None:
        self.status_label.setText("No se pudo actualizar")
        set_style_name(self.detail_label, "ErrorLabel")
        self.detail_label.setText(f"{error}\nTambién puedes descargarla desde GitHub.")
        self.progress_bar.hide()
        self.page_button.show()
        self.cancel_button.setText("Cerrar")
        self.cancel_button.setEnabled(True)

    def _open_page(self) -> None:
        open_url(self._release.url)
        super().reject()
