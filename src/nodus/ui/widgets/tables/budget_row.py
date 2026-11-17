"""A budgeted category with its bar underneath."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from nodus.models.budget import Budget
from nodus.ui.theme.design import Space
from nodus.ui.theme.theme import Theme
from nodus.ui.widgets.charts.budget_bar import BudgetBar
from nodus.ui.widgets.tables.category_line import CategoryLine


class BudgetRow(QWidget):
    """A budgeted category with its bar underneath; clicking it opens the category's
    transactions of the month. Callers add details to the right of the name on ``line``."""

    clicked = Signal()

    def __init__(self, budget: Budget, theme: Theme) -> None:
        super().__init__()
        self.budget = budget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, Space.XXS, 0, Space.S)
        layout.setSpacing(Space.XXS)
        self.line = CategoryLine(budget.category.color, budget.category.name)
        self.line.hovered.connect(self.line.set_highlighted)
        self.line.clicked.connect(self.clicked)
        self.bar = BudgetBar(theme, budget)
        bar_row = QHBoxLayout()
        bar_row.setContentsMargins(Space.XXL, 0, Space.S, 0)  # under the name, past the color dot
        bar_row.addWidget(self.bar)
        layout.addWidget(self.line)
        layout.addLayout(bar_row)
