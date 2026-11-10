"""The row of something that comes off an account on a calendar: a charge, a purchase in
installments."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from nodus.ui.theme.design import Space
from nodus.ui.widgets.color_dot import ColorDot
from nodus.ui.widgets.row_actions import ActionsFor, MoreButton, install_row_actions
from nodus.ui.widgets.style import set_style_property


class ScheduleRow(QWidget):
    """Category color, a title over its detail, the amount over a pill with when it is due,
    an optional button and the «⋯».

    Recurrentes lists charges and purchases in installments with the same row, so they line
    up and answer the mouse alike: ``actions`` is the menu of the right click and the «⋯»,
    and its main action runs on a double click.
    """

    def __init__(
        self,
        color: str,
        title: str,
        detail: str,
        amount_text: str,
        status_label: QLabel,
        actions: ActionsFor,
        button: QWidget | None = None,
    ) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Space.S, Space.S, Space.S, Space.S)
        layout.setSpacing(Space.M)
        layout.addWidget(ColorDot(color))

        texts = QVBoxLayout()
        texts.setSpacing(0)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("RowTitle")
        self.detail_label = QLabel(detail)
        set_style_property(self.detail_label, "muted", True)
        texts.addWidget(self.title_label)
        texts.addWidget(self.detail_label)
        layout.addLayout(texts, stretch=1)

        amounts = QVBoxLayout()
        amounts.setSpacing(0)
        self.amount_label = QLabel(amount_text)
        self.amount_label.setObjectName("RowAmount")
        self.amount_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.status_label = status_label
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        amounts.addWidget(self.amount_label)
        amounts.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(amounts)

        if button is not None:
            layout.addWidget(button)
        else:  # the button's room and its gap stay, so amounts line up across rows
            layout.addSpacing(layout.spacing() + MoreButton.SIZE)
        self.more_button = MoreButton(actions)
        layout.addWidget(self.more_button)
        install_row_actions(self, actions)
