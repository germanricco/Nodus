"""Strip under the top bar that announces a new version."""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from nodus.services.update_service import Release


class UpdateBanner(QFrame):
    """Says a new version is out and links to its download page.

    Hidden until there is something to say, and closing it lasts until the next start:
    the notice should be easy to see and just as easy to ignore.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("UpdateBanner")
        self.release: Release | None = None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 8, 16, 8)
        self.message_label = QLabel()
        layout.addWidget(self.message_label, stretch=1)
        self.download_button = QPushButton("Descargar")
        self.download_button.setObjectName("SmallButton")
        self.download_button.clicked.connect(self._open_download_page)
        layout.addWidget(self.download_button)
        self.close_button = QPushButton("×")
        self.close_button.setObjectName("BannerClose")
        self.close_button.setToolTip("Cerrar")
        self.close_button.clicked.connect(self.hide)
        layout.addWidget(self.close_button)
        self.hide()

    def show_release(self, release: Release) -> None:
        self.release = release
        self.message_label.setText(f"Hay una versión nueva de Nodus: la {release.version}.")
        self.show()

    def _open_download_page(self) -> None:
        if self.release is not None:
            QDesktopServices.openUrl(QUrl(self.release.url))
