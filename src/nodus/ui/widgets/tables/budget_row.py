"""A budgeted category with its bar underneath."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from nodus.models.budget import Budget
from nodus.ui.navigation import RecordLink
from nodus.ui.theme.design import Space
from nodus.ui.theme.theme import Theme
from nodus.ui.widgets.charts.budget_bar import BudgetBar
from nodus.ui.widgets.tables.category_line import CategoryLine


class BudgetRow(QWidget):
    """A budgeted category with its bar underneath; a click opens the category's page
    (``opened``). Callers add details to the right of the name on ``line``; ``start`` is
    where its bar begins (``ProgressStrip``)."""

    opened = Signal(object)  # RecordLink

    def __init__(self, budget: Budget, theme: Theme, start: float | None = None) -> None:
        super().__init__()
        self.budget = budget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, Space.XXS, 0, Space.S)
        layout.setSpacing(Space.XXS)
        self.link = RecordLink.category(budget.category.id)
        self.line = CategoryLine(budget.category.color, budget.category.name, link=self.link)
        self.line.opened.connect(self.opened)
        self.bar = BudgetBar(theme, budget, start)
        bar_row = QHBoxLayout()
        bar_row.setContentsMargins(Space.XXL, 0, Space.S, 0)  # under the name, past the color dot
        bar_row.addWidget(self.bar)
        layout.addWidget(self.line)
        layout.addLayout(bar_row)
