"""A headline figure with a small caption above it."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from nodus.models.money import Money
from nodus.ui.theme.design import Space
from nodus.ui.widgets.money_label import MoneyLabel
from nodus.ui.widgets.style import set_style_property

MISSING_RATE_TEXT = "Sin cotización"


class Stat(QWidget):
    """Caption plus amount, like "PATRIMONIO EN PESOS / $ 1.234,56".

    ``None`` means the figure needs an exchange rate that does not exist yet, and is
    shown as "Sin cotización" instead of a misleading number.
    """

    def __init__(self, caption: str, money: Money | None, large: bool = False) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.XXS)
        caption_label = QLabel(caption.upper())
        caption_label.setObjectName("StatCaption")
        layout.addWidget(caption_label)
        if money is None:
            value = QLabel(MISSING_RATE_TEXT)
            set_style_property(value, "muted", True)
        else:
            value = MoneyLabel(money)
            value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        value.setObjectName("StatValueLarge" if large else "StatValue")
        layout.addWidget(value)
