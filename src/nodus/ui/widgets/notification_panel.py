"""Popup under the bell that lists the notifications."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from nodus.services.notification_service import Notice, NoticeKind
from nodus.ui.theme.design import Layout, Line, Popup, Space
from nodus.ui.widgets.empty_state import EmptyState
from nodus.ui.widgets.style import clear_layout, set_style_property

# The notices the user can put off, with how the button says it.
DISMISS_LABELS = {
    NoticeKind.UPDATE: ("Descartar", "No volver a avisar de esta versión"),
    NoticeKind.BACKUP_REMINDER: ("Ahora no", "Volver a avisar a fin del mes que viene"),
    NoticeKind.GOAL_REACHED: ("Listo", "Quitar el aviso"),
}

ACTION_LABELS = {
    NoticeKind.UPDATE: "Actualizar",
    NoticeKind.STALE_RATE: "Ir a Ajustes",
    NoticeKind.BACKUP_FAILED: "Ir a Ajustes",
    NoticeKind.BACKUP_REMINDER: "Guardar copia…",
    NoticeKind.CHARGES_DUE: "Ver cargos",
    NoticeKind.BUDGET_OVER: "Ver presupuestos",
    NoticeKind.GOAL_REACHED: "Ver meta",
}


class NoticeRow(QWidget):
    """A notice: title, detail and its buttons."""

    def __init__(self, notice: Notice) -> None:
        super().__init__()
        self.notice = notice
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, Space.S, 0, Space.S)
        layout.setSpacing(Space.XXS)
        title = QLabel(notice.title)
        title.setObjectName("RowTitle")
        title.setWordWrap(True)
        detail = QLabel(notice.detail)
        detail.setWordWrap(True)
        set_style_property(detail, "muted", True)
        layout.addWidget(title)
        layout.addWidget(detail)
        buttons = QHBoxLayout()
        buttons.setSpacing(Space.S)
        self.news_button: QPushButton | None = None
        if notice.kind is NoticeKind.UPDATE and notice.notes:
            self.news_button = QPushButton("Qué trae")
            self.news_button.setObjectName("SmallButton")
            buttons.addWidget(self.news_button)
        self.action_button = QPushButton(ACTION_LABELS[notice.kind])
        self.action_button.setObjectName("SmallButton")
        buttons.addWidget(self.action_button)
        self.dismiss_button: QPushButton | None = None
        if notice.kind in DISMISS_LABELS:
            text, tooltip = DISMISS_LABELS[notice.kind]
            self.dismiss_button = QPushButton(text)
            self.dismiss_button.setObjectName("SmallButton")
            self.dismiss_button.setToolTip(tooltip)
            buttons.addWidget(self.dismiss_button)
        buttons.addStretch()
        layout.addSpacing(Space.XS)
        layout.addLayout(buttons)


class NotificationPanel(QFrame):
    """Lists the notices with their actions, or says there is nothing new.

    A popup: it closes on its own when the user clicks elsewhere.
    """

    action_requested = Signal(object)  # Notice
    dismiss_requested = Signal(object)  # Notice
    news_requested = Signal(object)  # Notice

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("NotificationPanel")
        self.setFixedWidth(Layout.NOTIFICATION_PANEL_WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Space.L, Space.M, Space.L, Space.M)
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
            self._rows.addWidget(EmptyState("Sin novedades.", compact=True))
        for index, notice in enumerate(notices):
            if index:
                separator = QFrame()
                separator.setObjectName("Separator")
                separator.setFixedHeight(Line.THIN)
                self._rows.addWidget(separator)
            row = NoticeRow(notice)
            row.action_button.clicked.connect(lambda _=False, n=notice: self._act(n))
            if row.news_button is not None:
                row.news_button.clicked.connect(lambda _=False, n=notice: self._show_news(n))
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
        corner = anchor.mapToGlobal(QPoint(anchor.width(), anchor.height() + Popup.PANEL_OFFSET))
        self.move(corner.x() - self.width(), corner.y())
        self.show()

    def _show_news(self, notice: Notice) -> None:
        self.hide()
        self.news_requested.emit(notice)

    def _act(self, notice: Notice) -> None:
        self.hide()
        self.action_requested.emit(notice)
