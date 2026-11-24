"""A category's row that opens its page, and the budgeted one with its bar underneath."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from nodus.i18n import _
from nodus.models.budget import Budget
from nodus.models.category import Category
from nodus.ui.navigation import RecordLink
from nodus.ui.theme.design import RowRole, RowSpace, Space
from nodus.ui.theme.theme import Theme
from nodus.ui.widgets.charts.budget_bar import BudgetBar
from nodus.ui.widgets.tables.category_line import CategoryLine
from nodus.ui.widgets.tables.row_actions import Effect, RowAction, install_row_actions


class CategoryRow(QWidget):
    """A category's name in a row that opens its page (``opened``): a click anywhere on
    it, and the whole row lights up, as every row that opens something
    (``navigation.py``). Callers add details to the right of the name on ``line``, more
    actions in ``actions`` and more lines under it in ``layout``."""

    opened = Signal(object)  # RecordLink

    def __init__(self, category: Category, height: int = RowRole.SINGLE) -> None:
        super().__init__()
        self.setMinimumHeight(height)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(0, RowSpace.EDGE, 0, RowSpace.EDGE)
        self.layout_.setSpacing(Space.XXS)
        self.layout_.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.link = RecordLink.category(category.id)
        # The line shows where the row leads («›»); the click is the row's, not the line's
        # alone, so what is under the name opens too and a click on the name opens once.
        self.line = CategoryLine(category.color, category.name, link=self.link, inside=True)
        self.line.hovered.disconnect(self.line.set_highlighted)
        install_row_actions(self, self.actions, open_on_click=self.link.detail.open_text)
        self.layout_.addWidget(self.line)

    @property
    def name(self) -> str:
        return self.line.name

    def actions(self) -> list[RowAction]:
        """Its category's page, as a click on the row."""
        return [
            RowAction(
                _("Abrir"), lambda: self.opened.emit(self.link), default=True, effect=Effect.OPEN
            )
        ]


class BudgetRow(CategoryRow):
    """A budgeted category with its bar underneath; ``start`` is where its bar begins
    (``ProgressStrip``)."""

    def __init__(self, budget: Budget, theme: Theme, start: float | None = None) -> None:
        # The name over its bar, together in the middle of a two-line row.
        super().__init__(budget.category, RowRole.DOUBLE)
        self.budget = budget
        self.bar = BudgetBar(theme, budget, start)
        bar_row = QHBoxLayout()
        bar_row.setContentsMargins(
            Space.XXL, 0, RowSpace.SIDE, 0
        )  # under the name, past the color dot
        bar_row.addWidget(self.bar)
        self.layout_.addLayout(bar_row)
