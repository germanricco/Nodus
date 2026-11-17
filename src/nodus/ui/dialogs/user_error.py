"""Errors told the way the user needs them: what happened and what to do about it.

The technical text (the system's own message) never leads: it waits behind «Ver
detalle», where it can be copied for a bug report. ``QMessageBox.setDetailedText`` is
not used because its button reads «Show Details…» in English.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nodus.ui.theme.design import Layout, Space
from nodus.ui.widgets.style import secondary_button

SHOW_DETAIL = "Ver detalle"
HIDE_DETAIL = "Ocultar detalle"


class ErrorDetail(QWidget):
    """A «Ver detalle» link that unfolds the technical text, read-only, with «Copiar».

    Hidden altogether while there is no detail to show.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.S)
        self.toggle_button = QPushButton(SHOW_DETAIL)
        self.toggle_button.setObjectName("LinkButton")
        self.toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_button.clicked.connect(self.toggle)
        layout.addWidget(self.toggle_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumHeight(Layout.ERROR_DETAIL_HEIGHT)
        layout.addWidget(self.text)
        self.copy_button = secondary_button("Copiar", self.copy)
        layout.addWidget(self.copy_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.set_detail("")

    def set_detail(self, detail: str) -> None:
        self.text.setPlainText(detail)
        self.setVisible(bool(detail))
        self._unfold(False)

    def toggle(self) -> None:
        self._unfold(self.text.isHidden())

    def copy(self) -> None:
        QGuiApplication.clipboard().setText(self.text.toPlainText())
        self.copy_button.setText("Copiado")

    def _unfold(self, unfolded: bool) -> None:
        self.text.setVisible(unfolded)
        self.copy_button.setVisible(unfolded)
        self.copy_button.setText("Copiar")
        self.toggle_button.setText(HIDE_DETAIL if unfolded else SHOW_DETAIL)


class UserErrorDialog(QDialog):
    """What went wrong, as a title-like sentence; what to do, under it; the technical
    detail folded away; and a single «Cerrar», since there is nothing to choose."""

    def __init__(
        self, title: str, what: str, how: str, detail: str = "", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(Layout.MESSAGE_MIN_WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Space.XXL, Space.XL, Space.XXL, Space.XL)
        layout.setSpacing(Space.M)
        self.what_label = QLabel(what)
        self.what_label.setObjectName("DialogTitle")
        self.what_label.setWordWrap(True)
        layout.addWidget(self.what_label)
        self.how_label = QLabel(how)
        self.how_label.setWordWrap(True)
        layout.addWidget(self.how_label)
        self.detail = ErrorDetail()
        self.detail.set_detail(detail)
        layout.addWidget(self.detail)
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.close_button = QPushButton("Cerrar")
        self.close_button.setObjectName("PrimaryButton")
        self.close_button.setDefault(True)
        self.close_button.clicked.connect(self.accept)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)


def user_error(parent: QWidget | None, title: str, what: str, how: str, detail: str = "") -> None:
    """Tells the user that something failed: ``what`` happened, ``how`` to fix it, and
    the system's ``detail`` folded behind «Ver detalle»."""
    UserErrorDialog(title, what, how, detail, parent).exec()
