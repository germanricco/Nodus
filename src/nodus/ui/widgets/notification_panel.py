"""Popup under the bell that lists the notifications."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from nodus.services.notification_service import Notice, NoticeKind
from nodus.ui.widgets.style import clear_layout, set_style_property

ACTION_LABELS = {
    NoticeKind.UPDATE: "Descargar",
    NoticeKind.STALE_RATE: "Ir a Ajustes",
    NoticeKind.BACKUP_FAILED: "Ir a Ajustes",
    NoticeKind.CHARGES_DUE: "Ver cargos",
}
WIDTH = 340


class NoticeRow(QWidget):
    """A notice: title, detail and its buttons."""

    def __init__(self, notice: Notice) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(2)
        title = QLabel(notice.title)
        title.setObjectName("RowTitle")
        title.setWordWrap(True)
        detail = QLabel(notice.detail)
        detail.setWordWrap(True)
        set_style_property(detail, "muted", True)
        layout.addWidget(title)
        layout.addWidget(detail)
        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self.action_button = QPushButton(ACTION_LABELS[notice.kind])
        self.action_button.setObjectName("SmallButton")
        buttons.addWidget(self.action_button)
        self.dismiss_button: QPushButton | None = None
        if notice.kind is NoticeKind.UPDATE:
            self.dismiss_button = QPushButton("Descartar")
            self.dismiss_button.setObjectName("SmallButton")
            self.dismiss_button.setToolTip("No volver a avisar de esta versión")
            buttons.addWidget(self.dismiss_button)
        buttons.addStretch()
        layout.addSpacing(4)
        layout.addLayout(buttons)


class NotificationPanel(QFrame):
    """Lists the notices with their actions, or says there is nothing new.

    A popup: it closes on its own when the user clicks elsewhere.
    """

    action_requested = Signal(object)  # Notice
    dismiss_requested = Signal(object)  # Notice

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("NotificationPanel")
        self.setFixedWidth(WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(0)
        title = QLabel("NOTIFICACIONES")
        title.setObjectName("CardTitle")
        layout.addWidget(title)
        self._rows = QVBoxLayout()
        self._rows.setSpacing(0)
        layout.addLayout(self._rows)
        self.rows: list[NoticeRow] = []

    def set_notices(self, notices: list[Notice]) -> None:
        clear_layout(self._rows)
        self.rows = []
        if not notices:
            empty = QLabel("Sin novedades")
            set_style_property(empty, "muted", True)
            empty.setContentsMargins(0, 10, 0, 4)
            self._rows.addWidget(empty)
        for index, notice in enumerate(notices):
            if index:
                separator = QFrame()
                separator.setObjectName("Separator")
                separator.setFixedHeight(1)
                self._rows.addWidget(separator)
            row = NoticeRow(notice)
            row.action_button.clicked.connect(lambda _=False, n=notice: self._act(n))
            if row.dismiss_button is not None:
                row.dismiss_button.clicked.connect(
                    lambda _=False, n=notice: self.dismiss_requested.emit(n)
                )
            self._rows.addWidget(row)
            self.rows.append(row)
        self.adjustSize()

    def open_below(self, anchor: QWidget) -> None:
        """Shows the panel under ``anchor``, its right edge aligned with the anchor's."""
        self.adjustSize()
        corner = anchor.mapToGlobal(QPoint(anchor.width(), anchor.height() + 6))
        self.move(corner.x() - self.width(), corner.y())
        self.show()

    def _act(self, notice: Notice) -> None:
        self.hide()
        self.action_requested.emit(notice)
