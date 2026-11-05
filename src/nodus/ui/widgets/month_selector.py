"""Previous/next control to move between months."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from nodus.models.period import Month
from nodus.ui.formatting import format_month


class MonthSelector(QWidget):
    """Shows "‹ Noviembre 2026 ›" and emits ``month_changed`` when the user moves."""

    month_changed = Signal(object)  # Month

    def __init__(self, month: Month | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.previous_button = self._arrow("‹", "Mes anterior")
        self.next_button = self._arrow("›", "Mes siguiente")
        self._label = QLabel()
        self._label.setObjectName("MonthLabel")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.previous_button)
        layout.addWidget(self._label)
        layout.addWidget(self.next_button)

        self.previous_button.clicked.connect(lambda: self.set_month(self._month.previous()))
        self.next_button.clicked.connect(lambda: self.set_month(self._month.next()))
        self._month = month or Month.of(date.today())
        self._label.setText(format_month(self._month))

    def month(self) -> Month:
        return self._month

    def set_month(self, month: Month) -> None:
        if month == self._month:
            return
        self._month = month
        self._label.setText(format_month(month))
        self.month_changed.emit(month)

    @staticmethod
    def _arrow(text: str, tooltip: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("SmallButton")
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button
