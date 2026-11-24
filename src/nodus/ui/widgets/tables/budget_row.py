"""A budgeted category with its bar underneath."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from nodus.i18n import _
from nodus.models.budget import Budget
from nodus.ui.navigation import RecordLink
from nodus.ui.theme.design import RowRole, RowSpace, Space
from nodus.ui.theme.theme import Theme
from nodus.ui.widgets.charts.budget_bar import BudgetBar
from nodus.ui.widgets.tables.category_line import CategoryLine
from nodus.ui.widgets.tables.row_actions import Effect, RowAction, install_row_actions


class BudgetRow(QWidget):
    """A budgeted category with its bar underneath. A click anywhere on it, the name or
    the bar, opens the category's page (``opened``), and the whole row lights up, as every
    row that opens something (``navigation.py``). Callers add details to the right of the
    name on ``line`` and more actions in ``actions``; ``start`` is where its bar begins
    (``ProgressStrip``)."""

    opened = Signal(object)  # RecordLink

    def __init__(self, budget: Budget, theme: Theme, start: float | None = None) -> None:
        super().__init__()
        self.budget = budget
        # The name over its bar, together in the middle of a two-line row.
        self.setMinimumHeight(RowRole.DOUBLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, RowSpace.EDGE, 0, RowSpace.EDGE)
        layout.setSpacing(Space.XXS)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.link = RecordLink.category(budget.category.id)
        # The line shows where the row leads («›»); the click is the row's, not the line's
        # alone, so the bar opens too and a click on the name opens once.
        self.line = CategoryLine(
            budget.category.color, budget.category.name, link=self.link, inside=True
        )
        self.line.hovered.disconnect(self.line.set_highlighted)
        install_row_actions(self, self.actions, open_on_click=self.link.detail.open_text)
        self.bar = BudgetBar(theme, budget, start)
        bar_row = QHBoxLayout()
        bar_row.setContentsMargins(
            Space.XXL, 0, RowSpace.SIDE, 0
        )  # under the name, past the color dot
        bar_row.addWidget(self.bar)
        layout.addWidget(self.line)
        layout.addLayout(bar_row)

    def actions(self) -> list[RowAction]:
        """Its category's page, as a click on the row."""
        return [
            RowAction(
                _("Abrir"), lambda: self.opened.emit(self.link), default=True, effect=Effect.OPEN
            )
        ]
