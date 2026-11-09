"""Previous/next control with a menu of ready-made periods and a free range of dates."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QMenu, QPushButton, QSizePolicy, QWidget

from nodus.models.period import Period, QuickPeriod
from nodus.ui.dialogs.date_range_dialog import DateRangeDialog
from nodus.ui.theme.design import Space


class PeriodSelector(QWidget):
    """Shows "‹ Noviembre 2026 ▾ ›". The arrows move by the period's length; the middle
    button offers the quick choices (current month, last 3 months, this year…) and
    "Personalizado…", any range of days.

    With ``quick_choices`` off it moves month by month only, and the middle button
    returns to the current month, for screens that always show a single month.

    Emits ``period_changed`` whenever the period changes.
    """

    period_changed = Signal(object)  # Period

    def __init__(
        self,
        period: Period | None = None,
        quick_choices: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.XS)
        self.previous_button = self._arrow("‹", "Período anterior")
        self.next_button = self._arrow("›", "Período siguiente")
        self.period_button = QPushButton()
        self.period_button.setObjectName("PeriodButton")
        self.period_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quick_menu = QMenu(self)
        for quick in QuickPeriod:
            action = self.quick_menu.addAction(quick.value)
            action.triggered.connect(lambda _=False, q=quick: self.choose(q))
        self.quick_menu.addSeparator()
        self.quick_menu.addAction("Personalizado…").triggered.connect(self.choose_range)
        if quick_choices:
            self.period_button.setMenu(self.quick_menu)
        else:
            self.period_button.setToolTip("Volver al mes actual")
            self.period_button.clicked.connect(lambda: self.choose(QuickPeriod.CURRENT_MONTH))
        layout.addWidget(self.previous_button)
        layout.addWidget(self.period_button)
        layout.addWidget(self.next_button)
        # Never squeezed by its neighbours, or the label gets cut off.
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.previous_button.clicked.connect(lambda: self.set_period(self._period.shifted(-1)))
        self.next_button.clicked.connect(lambda: self.set_period(self._period.shifted(1)))
        self._period = period or QuickPeriod.CURRENT_MONTH.period(date.today())
        self.period_button.setText(self._period.label())

    def period(self) -> Period:
        return self._period

    def set_period(self, period: Period) -> None:
        if period == self._period:
            return
        self._period = period
        self.period_button.setText(period.label())
        self.period_changed.emit(period)

    def choose(self, quick: QuickPeriod) -> None:
        self.set_period(quick.period(date.today()))

    def choose_range(self) -> None:
        """Asks for a first and a last day, starting on the period shown."""
        dialog = DateRangeDialog(self._period, self.window())
        if dialog.exec():
            self.set_period(dialog.period)

    @staticmethod
    def _arrow(text: str, tooltip: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("SmallButton")
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button
