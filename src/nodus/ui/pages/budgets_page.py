"""Budgets section: each category's monthly limit, what was spent and how the month goes."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
)

from nodus.i18n import N_, _, ngettext
from nodus.models.budget import Budget, BudgetState
from nodus.models.category import Category
from nodus.models.period import Month, Period, format_month, format_month_in_sentence
from nodus.services.container import Services
from nodus.services.planning.budget_service import MonthBudgets
from nodus.services.reports.dashboard_service import CategoryTotal
from nodus.ui.dialogs.budget_dialog import BudgetDialog
from nodus.ui.dialogs.confirm import delete_with_confirm
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import PageId, RecordLink, TransactionFocus
from nodus.ui.pages.base.page import Page
from nodus.ui.period_selector import PeriodSelector
from nodus.ui.text.labels import days_left_text, unconverted_note
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.charts.budget_bar import budget_pill, usage_text
from nodus.ui.widgets.charts.chart_base import shown_fractions
from nodus.ui.widgets.empty_state import empty_page_card
from nodus.ui.widgets.figure_row import FigureRow
from nodus.ui.widgets.figure_tile import FigureTile
from nodus.ui.widgets.style import amount_label, clear_layout, hint_label, muted_label
from nodus.ui.widgets.tables.budget_row import BudgetRow
from nodus.ui.widgets.tables.category_line import CategoryLine
from nodus.ui.widgets.tables.row_actions import Effect, MoreButton, RowAction, install_row_actions

EMPTY_TEXT = N_(
    "Ponle un límite mensual a las categorías que quieres cuidar, como el supermercado o "
    "las salidas. Nodus te muestra cuánto llevas gastado, si vas más rápido que el mes y "
    "te avisa cuando te pasas."
)


class BudgetPageRow(BudgetRow):
    """A budget row with the details the page has room for: how much is used, what is
    left and a menu to change or remove the limit."""

    transactions_requested = Signal()
    edit_requested = Signal()
    remove_requested = Signal()

    def __init__(self, budget: Budget, theme: Theme, start: float | None = None) -> None:
        super().__init__(budget, theme, start)
        self.usage_label = self.line.add(muted_label(usage_text(budget)))
        self.pill = self.line.add(budget_pill(budget))
        self.more_button = self.line.add(MoreButton(self.actions))
        install_row_actions(self, self.actions)
        # The whole row lights up, as every row with a menu; not its name line alone.
        self.line.hovered.disconnect(self.line.set_highlighted)

    def actions(self) -> list[RowAction]:
        """Its category's page first, as a click on the row; its movements of the month;
        then changing or removing it."""
        return [
            RowAction(
                _("Abrir"),
                lambda: self.opened.emit(self.link),
                default=True,
                effect=Effect.OPEN,
            ),
            RowAction(
                _("Ver movimientos"), self.transactions_requested.emit, "list", effect=Effect.OPEN
            ),
            RowAction(_("Cambiar límite"), self.edit_requested.emit, "pencil", effect=Effect.OPEN),
            RowAction(
                _("Quitar presupuesto"),
                self.remove_requested.emit,
                "trash",
                destructive=True,
                effect=Effect.CONFIRMED,
            ),
        ]


class BudgetsPage(Page):
    """A month at a time: the totals on top, the budgets from the most to the least used,
    and the spending of categories that have no budget."""

    transactions_requested = Signal(object)  # TransactionFocus
    record_requested = Signal(object)  # RecordLink

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__(PageId.BUDGETS.label)
        self._services = services
        self._event_bus = event_bus
        self._theme_manager = theme_manager
        self.month_selector = PeriodSelector(quick_choices=False)
        self.add_header_widget(self.month_selector)
        self.create_button = self.add_header_button(_("Agregar presupuesto"), primary=True)
        self.create_button.clicked.connect(lambda: self.open_budget_dialog())

        self._sections = self.scrolling_body()
        self.rows: list[BudgetPageRow] = []
        self._shown: dict[int | None, float] = {}  # each bar, where its next one starts
        self.unbudgeted_rows: list[CategoryLine] = []
        self.limit_label = QLabel()
        self.spent_label = QLabel()
        self.remaining_label = QLabel()
        self._today: date | None = None

        self.month_selector.period_changed.connect(lambda _period: self.refresh(self._today))

    @property
    def month(self) -> Month:
        return self.month_selector.period().first_month

    def show_month(self, month: Month) -> None:
        self.month_selector.set_period(Period.of_months(month))

    def refresh(self, today: date | None = None) -> None:
        """``today`` is fixed by tests, and kept by later refreshes; otherwise the
        real date is used."""
        self._today = today = today or self._today
        today = today or date.today()
        self._shown = shown_fractions({row.budget.category.id: row.bar for row in self.rows})
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
        text = _(
            "«{name}» deja de tener presupuesto desde {month}. Los meses anteriores "
            "conservan su límite."
        ).format(name=category.name, month=format_month_in_sentence(self.month))
        delete_with_confirm(
            self.window(),
            _("Quitar presupuesto"),
            text,
            lambda: self._services.budgets.remove(category.id, self.month),
            self._event_bus.budgets_changed,
        )

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
        tiles = FigureRow()
        for caption, value in (
            (_("Presupuestado"), self.limit_label),
            (_("Gastado"), self.spent_label),
            (_("Excedido en") if over else _("Quedan"), self.remaining_label),
        ):
            tiles.add_tile(FigureTile(caption, value))
        card.body.addWidget(tiles)
        if month.unconverted:
            note = hint_label(unconverted_note(month.unconverted))
            card.body.addWidget(note)
        return card

    def _budgets_card(self, month: MonthBudgets) -> Card:
        over = sum(1 for b in month.budgets if b.state is BudgetState.OVER)
        title = _("Presupuestos ({count})").format(count=len(month.budgets))
        if over:
            title += " · " + ngettext("{count} excedido", "{count} excedidos", over).format(
                count=over
            )
        card = Card(title)
        theme = self._theme_manager.theme
        for budget in month.budgets:
            row = BudgetPageRow(budget, theme, self._shown.get(budget.category.id))
            category = budget.category
            row.opened.connect(self.record_requested)
            row.transactions_requested.connect(lambda c=category: self._show_transactions(c))
            row.edit_requested.connect(lambda c=category: self.open_budget_dialog(c))
            row.remove_requested.connect(lambda c=category: self.remove_budget(c))
            card.body.addWidget(row)
            self.rows.append(row)
        return card

    def _unbudgeted_card(self, totals: list[CategoryTotal]) -> Card:
        card = Card(_("Sin presupuesto"))
        hint = hint_label(_("Lo gastado en el mes en categorías sin límite."))
        card.body.addWidget(hint)
        for total in totals:
            category = total.category
            line = CategoryLine(
                category.color, category.name, link=RecordLink.category(category.id)
            )
            line.opened.connect(self.record_requested)
            amount = amount_label(total.total)
            line.add(amount)
            button = QPushButton(_("Poner límite"))
            button.setObjectName("SmallButton")
            button.clicked.connect(lambda _checked=False, c=category: self.open_budget_dialog(c))
            line.add(button)
            card.body.addWidget(line)
            self.unbudgeted_rows.append(line)
        return card

    def _empty_state(self) -> Card:
        card, _state = empty_page_card(_("Todavía no hay presupuestos"), _(EMPTY_TEXT))
        return card
