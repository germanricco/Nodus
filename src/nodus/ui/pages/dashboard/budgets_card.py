"""Inicio: the budgets closest to their limit."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout

from nodus.models.period import Month, format_month
from nodus.services.container import Services
from nodus.ui.text.labels import days_left_text
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card, card_header, see_all_link
from nodus.ui.widgets.charts.budget_bar import spent_of_limit
from nodus.ui.widgets.charts.chart_base import shown_fractions
from nodus.ui.widgets.style import clear_layout, muted_label
from nodus.ui.widgets.tables.budget_row import BudgetRow

# Budgets on the dashboard, the closest to their limit first; the page has them all.
BUDGETS_COUNT = 4


class BudgetsCard(Card):
    """The budgets closest to their limit in a month, for a glance; the rest are on the
    budgets page. Hidden when the month has no budgets."""

    category_clicked = Signal(object)  # category id
    see_all_requested = Signal()

    def __init__(self, services: Services, theme_manager: ThemeManager) -> None:
        super().__init__()
        self._services = services
        self._theme_manager = theme_manager
        header = card_header(self, "Presupuestos")
        self.when_label = muted_label("")
        header.addWidget(self.when_label)
        self.see_all_button = see_all_link(header, "Ver todos", self.see_all_requested)
        self._rows = QVBoxLayout()
        self._rows.setSpacing(0)
        self.body.addLayout(self._rows)
        self.body.addStretch()
        self.rows: list[BudgetRow] = []

    def show_month(self, month: Month, today: date) -> None:
        budgets = self._services.budgets.month_budgets(month, today)
        self.setVisible(bool(budgets.budgets))
        self.when_label.setText(days_left_text(month, today) or format_month(month))
        shown = shown_fractions({row.budget.category.id: row.bar for row in self.rows})
        clear_layout(self._rows)
        self.rows = []
        theme = self._theme_manager.theme
        for budget in budgets.budgets[:BUDGETS_COUNT]:
            row = BudgetRow(budget, theme, shown.get(budget.category.id))
            row.line.add(muted_label(spent_of_limit(budget, compact=True)))
            row.clicked.connect(lambda c=budget.category.id: self.category_clicked.emit(c))
            self._rows.addWidget(row)
            self.rows.append(row)
