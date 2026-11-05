"""Label that shows an amount colored by its sign."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from nodus.models.money import Money
from nodus.ui.widgets.style import set_style_property


class MoneyLabel(QLabel):
    """Shows a ``Money`` in Argentine format, red when negative.

    With ``highlight_positive`` positive amounts turn green too, which suits income and
    expense lists; balances leave them in the normal text color.
    """

    def __init__(
        self, money: Money | None = None, highlight_positive: bool = False, parent: QWidget = None
    ) -> None:
        super().__init__(parent)
        self._highlight_positive = highlight_positive
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if money is not None:
            self.set_money(money)

    def set_money(self, money: Money) -> None:
        self.setText(money.format())
        set_style_property(self, "tone", self._tone(money))

    def _tone(self, money: Money) -> str:
        if money.is_negative:
            return "negative"
        if self._highlight_positive and not money.is_zero:
            return "positive"
        return "neutral"
