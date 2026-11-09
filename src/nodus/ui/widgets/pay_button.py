"""The «✓» that pays a recurring charge from its row, in Recurrentes and on the Dashboard."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtWidgets import QPushButton, QSizePolicy, QWidget

from nodus.ui.theme.icons import icon
from nodus.ui.theme.theme_manager import active_theme
from nodus.ui.widgets.row_actions import MoreButton

PAY_TIP = "Registrar el pago"


class PayButton(QPushButton):
    """A small soft green button with a check, as MoneyMatter's «Mark as paid»: the one
    action of a charge that stays on its row, because paying is what the list is for. The
    rest (skip, edit, pause, delete) is in the row's menu.

    The same size as the «⋯», so both line up at the end of every row. A paused charge
    hides it but keeps its room, so the columns stay aligned.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PayButton")
        self.setToolTip(PAY_TIP)
        self.setAccessibleName(PAY_TIP)
        self.setFixedSize(MoreButton.SIZE, MoreButton.SIZE)
        self.setIconSize(QSize(18, 18))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        policy = self.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        self.setSizePolicy(QSizePolicy(policy))
        self._tint()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            self._tint()

    def _tint(self) -> None:
        self.setIcon(icon("pay", active_theme().income))
