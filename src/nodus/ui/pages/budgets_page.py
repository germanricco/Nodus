"""Budgets section: each category's monthly limit, what was spent and how the month goes."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from nodus.models.budget import Budget, BudgetState
from nodus.models.category import Category
from nodus.models.period import Month, Period, format_month
from nodus.services.budget_service import MonthBudgets
from nodus.services.container import Services
from nodus.services.dashboard_service import CategoryTotal
from nodus.ui.dialogs.budget_dialog import BudgetDialog
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.event_bus import EventBus
from nodus.ui.labels import days_left_text, unconverted_note
from nodus.ui.navigation import TransactionFocus
from nodus.ui.pages.dashboard_cards import BudgetRow, CategoryLine, FigureTile, muted_label
from nodus.ui.pages.page import Page
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.budget_bar import budget_pill, usage_text
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.period_selector import PeriodSelector
from nodus.ui.widgets.row_actions import MoreButton, RowAction, install_context_menu
from nodus.ui.widgets.style import clear_layout, set_style_property

EMPTY_TEXT = (
    "Ponle un límite mensual a las categorías que quieres cuidar, como el supermercado o "
    "las salidas. Nodus te muestra cuánto llevas gastado, si vas más rápido que el mes y "
    "te avisa cuando te pasas."
)


class BudgetPageRow(BudgetRow):
    """A budget row with the details the page has room for: how much is used, what is
    left and a menu to change or remove the limit."""

    edit_requested = Signal()
    remove_requested = Signal()

    def __init__(self, budget: Budget, theme: Theme) -> None:
        super().__init__(budget, theme)
        self.usage_label = self.line.add(muted_label(usage_text(budget)))
        self.pill = self.line.add(budget_pill(budget))
        self.more_button = self.line.add(MoreButton(self.actions))
        install_context_menu(self, self.actions)

    def actions(self) -> list[RowAction]:
        return [
            RowAction("Cambiar límite", self.edit_requested.emit, "pencil"),
            RowAction("Quitar presupuesto", self.remove_requested.emit, "trash", destructive=True),
        ]


class BudgetsPage(Page):
    """A month at a time: the totals on top, the budgets from the most to the least used,
    and the spending of categories that have no budget."""

    transactions_requested = Signal(object)  # TransactionFocus

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__("Presupuestos")
        self._services = services
        self._event_bus = event_bus
        self._theme_manager = theme_manager
        self.month_selector = PeriodSelector(quick_choices=False)
        self.add_header_widget(self.month_selector)
        self.create_button = self.add_header_button("Agregar presupuesto", primary=True)
        self.create_button.clicked.connect(lambda: self.open_budget_dialog())

        container = QWidget()
        self._sections = QVBoxLayout(container)
        self._sections.setContentsMargins(0, 0, 0, 0)
        self._sections.setSpacing(16)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        self.content_layout.addWidget(scroll)
        self.rows: list[BudgetPageRow] = []
        self.unbudgeted_rows: list[CategoryLine] = []
        self.limit_label = QLabel()
        self.spent_label = QLabel()
        self.remaining_label = QLabel()
        self._today: date | None = None

        self.month_selector.period_changed.connect(lambda _period: self.refresh(self._today))
        theme_manager.theme_changed.connect(lambda _theme: self.refresh(self._today))
        for signal in (
            event_bus.budgets_changed,
            event_bus.transactions_changed,
            event_bus.categories_changed,
            event_bus.exchange_rates_changed,
        ):
            signal.connect(lambda: self.refresh(self._today))

    @property
    def month(self) -> Month:
        return self.month_selector.period().first_month

    def show_month(self, month: Month) -> None:
        self.month_selector.set_period(Period.of_months(month))

    def refresh(self, today: date | None = None) -> None:
        """``today`` is fixed by tests; otherwise the real date is used."""
        self._today = today
        today = today or date.today()
        clear_layout(self._sections)
        self.rows, self.unbudgeted_rows = [], []
        month = self._services.budgets.month_budgets(self.month, today)
        if not month.budgets:
            self._sections.addWidget(self._empty_state())
        else:
            self._sections.addWidget(self._summary_card(month, today))
            self._sections.addWidget(self._budgets_card(month))
        if month.unbudgeted:
            self._sections.addWidget(self._unbudgeted_card(month.unbudgeted))
        self._sections.addStretch()

    # Actions

    def open_budget_dialog(self, category: Category | None = None) -> None:
        BudgetDialog(
            self._services, self._event_bus, self.month, category, parent=self.window()
        ).exec()

    def remove_budget(self, category: Category) -> None:
        text = (
            f"«{category.name}» deja de tener presupuesto desde "
            f"{format_month(self.month).lower()}. Los meses anteriores conservan su límite."
        )
        if not confirm(self.window(), "Quitar presupuesto", text, action="Quitar"):
            return
        self._services.budgets.remove(category.id, self.month)
        self._event_bus.budgets_changed.emit()

    def _show_transactions(self, category: Category) -> None:
        self.transactions_requested.emit(
            TransactionFocus(Period.of_months(self.month), category.id)
        )

    # Building

    def _summary_card(self, month: MonthBudgets, today: date) -> Card:
        days_left = days_left_text(month.month, today)
        card = Card(format_month(month.month) + (f" · {days_left}" if days_left else ""))
        over = month.remaining.is_negative
        self.limit_label = QLabel(month.limit.format())
        self.spent_label = QLabel(month.spent.format())
        self.remaining_label = QLabel((-month.remaining if over else month.remaining).format())
        tiles = QHBoxLayout()
        tiles.setSpacing(8)
        for caption, value in (
            ("Presupuestado", self.limit_label),
            ("Gastado", self.spent_label),
            ("Excedido en" if over else "Quedan", self.remaining_label),
        ):
            tiles.addWidget(FigureTile(caption, value), stretch=1)
        card.body.addLayout(tiles)
        if month.unconverted:
            note = QLabel(unconverted_note(month.unconverted))
            note.setObjectName("FieldHint")
            card.body.addWidget(note)
        return card

    def _budgets_card(self, month: MonthBudgets) -> Card:
        over = sum(1 for b in month.budgets if b.state is BudgetState.OVER)
        title = f"Presupuestos ({len(month.budgets)})"
        if over:
            title += f" · {over} excedido" + ("s" if over > 1 else "")
        card = Card(title)
        theme = self._theme_manager.theme
        for budget in month.budgets:
            row = BudgetPageRow(budget, theme)
            category = budget.category
            row.clicked.connect(lambda c=category: self._show_transactions(c))
            row.edit_requested.connect(lambda c=category: self.open_budget_dialog(c))
            row.remove_requested.connect(lambda c=category: self.remove_budget(c))
            card.body.addWidget(row)
            self.rows.append(row)
        return card

    def _unbudgeted_card(self, totals: list[CategoryTotal]) -> Card:
        card = Card("Sin presupuesto")
        hint = QLabel("Lo gastado en el mes en categorías sin límite.")
        hint.setObjectName("FieldHint")
        card.body.addWidget(hint)
        for total in totals:
            category = total.category
            line = CategoryLine(category.color, category.name)
            line.hovered.connect(line.set_highlighted)
            line.clicked.connect(lambda c=category: self._show_transactions(c))
            amount = QLabel(total.total.format())
            amount.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            line.add(amount)
            button = QPushButton("Poner límite")
            button.setObjectName("SmallButton")
            button.clicked.connect(lambda _=False, c=category: self.open_budget_dialog(c))
            line.add(button)
            card.body.addWidget(line)
            self.unbudgeted_rows.append(line)
        return card

    def _empty_state(self) -> Card:
        card = Card()
        title = QLabel("Aún no hay presupuestos")
        title.setObjectName("RowTitle")
        text = QLabel(EMPTY_TEXT)
        text.setWordWrap(True)
        set_style_property(text, "muted", True)
        card.body.addWidget(title)
        card.body.addWidget(text)
        return card
