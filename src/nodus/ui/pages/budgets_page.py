"""Budgets section: each category's monthly limit, what was spent and how the month goes."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QScrollArea, QWidget

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
from nodus.ui.text.labels import days_left_text, names_text, unconverted_note
from nodus.ui.theme.design import Space
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.charts.budget_bar import BudgetBar, budget_pill, share_of_limit, usage_text
from nodus.ui.widgets.charts.chart_base import ProgressStrip, shown_fractions
from nodus.ui.widgets.empty_state import empty_page_card
from nodus.ui.widgets.flow_layout import FlowLayout
from nodus.ui.widgets.hero_figure import HeroFigure
from nodus.ui.widgets.money_label import MoneyLabel
from nodus.ui.widgets.style import (
    amount_label,
    bring_into_view,
    clear_layout,
    hint_label,
    muted_label,
)
from nodus.ui.widgets.tables.budget_row import BudgetRow
from nodus.ui.widgets.tables.category_line import CategoryLine
from nodus.ui.widgets.tables.row_actions import Effect, MoreButton, RowAction
from nodus.ui.widgets.tables.row_layout import row_list

EMPTY_TEXT = N_(
    "Ponle un límite mensual a las categorías que quieres cuidar, como el supermercado o "
    "las salidas. Nodus te muestra cuánto llevas gastado, si vas más rápido que el mes y "
    "te avisa cuando te pasas."
)


def remaining_caption(month: MonthBudgets) -> str:
    """What the header's figure is: what is left to spend, what was left over in a
    month gone by, or how far the limits were passed."""
    if month.remaining.is_negative:
        return N_("Te pasaste en")
    if month.days_left == 0:
        return N_("Te sobraron")
    return N_("Te quedan para gastar")


def over_text(month: MonthBudgets) -> str:
    """ "Ocio se pasó $ 10.500,00", or "2 presupuestos excedidos: Ocio y Servicios"."""
    over = month.over
    if len(over) == 1:
        return _("{name} se pasó {amount}").format(
            name=over[0].category.name, amount=(-over[0].remaining).format()
        )
    return ngettext(
        "{count} presupuesto excedido: {names}",
        "{count} presupuestos excedidos: {names}",
        len(over),
    ).format(count=len(over), names=names_text([b.category.name for b in over]))


def unbudgeted_text(month: MonthBudgets) -> str:
    """ "Vivienda y Educación gastaron $ 610.000,00 sin presupuesto": what the limits do
    not see, so the figure above is not taken for all that can be spent."""
    names = [t.category.name for t in month.unbudgeted]
    return ngettext(
        "{names} gastó {amount} sin presupuesto",
        "{names} gastaron {amount} sin presupuesto",
        len(names),
    ).format(names=names_text(names), amount=month.unbudgeted_spent.format())


class BudgetPageRow(BudgetRow):
    """A budget row with what is left, in its pill, and a menu to change or remove the
    limit. How much of it went is in the pill's tooltip and on the category's page."""

    transactions_requested = Signal()
    edit_requested = Signal()
    remove_requested = Signal()

    def __init__(self, budget: Budget, theme: Theme, start: float | None = None) -> None:
        super().__init__(budget, theme, start)
        self.pill = self.line.add(budget_pill(budget))
        self.pill.setToolTip(usage_text(budget))
        self.more_button = self.line.add(MoreButton(self.actions))

    def actions(self) -> list[RowAction]:
        """Its category's page first, as a click on the row; its movements of the month;
        then changing or removing it."""
        return [
            *super().actions(),
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
    """A month at a time. On top, the answer to «how much can I still spend?»: what is
    left of all the budgets, how much a day, the month's bar and, only when there are,
    the budgets passed and the spending no budget sees (plan 029a, 5.3). Under it, the
    budgets from the most to the least used, and the categories without one."""

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
        self.add_header_filter(self.month_selector)
        self.create_button = self.add_header_button(_("Agregar presupuesto"), primary=True)
        self.create_button.clicked.connect(lambda: self.open_budget_dialog())

        self._sections = self.scrolling_body()
        self.rows: list[BudgetPageRow] = []
        self._shown: dict[int | None, float] = {}  # each bar, where its next one starts
        self.unbudgeted_rows: list[CategoryLine] = []
        self.unbudgeted_card: Card | None = None
        self.remaining_label = MoneyLabel()
        self.per_day_label = muted_label("")
        self.share_label = muted_label("")
        self.over_label = muted_label("")
        self.unbudgeted_link = QPushButton()
        self.total_bar: BudgetBar | None = None
        self._scroll: QScrollArea | None = None
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
        bars: dict[int | None, ProgressStrip] = {r.budget.category.id: r.bar for r in self.rows}
        if self.total_bar is not None:
            bars[None] = self.total_bar  # the month's bar, keyed apart from any category
        self._shown = shown_fractions(bars)
        clear_layout(self._sections)
        self.rows, self.unbudgeted_rows = [], []
        self.total_bar = self.unbudgeted_card = None
        month = self._services.budgets.month_budgets(self.month, today)
        if not month.budgets:
            self._sections.addWidget(self._empty_state())
        else:
            self._sections.addWidget(self._summary_card(month, today))
            self._sections.addWidget(self._budgets_card(month))
        if month.unbudgeted:
            self.unbudgeted_card = self._unbudgeted_card(month.unbudgeted)
            self._sections.addWidget(self.unbudgeted_card)
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
        total = month.total
        self.remaining_label = MoneyLabel(month.remaining)
        per_day = month.per_day
        self.per_day_label = muted_label(
            _("Unos {amount} por día").format(amount=per_day.format()) if per_day else ""
        )
        card.body.addWidget(
            HeroFigure(_(remaining_caption(month)), self.remaining_label, self.per_day_label)
        )
        self.per_day_label.setVisible(per_day is not None)  # once in place, never a window

        bar_row = QHBoxLayout()
        bar_row.setSpacing(Space.M)
        self.total_bar = BudgetBar(self._theme_manager.theme, total, self._shown.get(None))
        bar_row.addWidget(self.total_bar, stretch=1)
        self.share_label = muted_label(share_of_limit(total))
        bar_row.addWidget(self.share_label)
        card.body.addSpacing(Space.XS)
        card.body.addLayout(bar_row)

        # Only what happens, and on a second line when the window is narrow.
        alerts = QWidget()
        flow = FlowLayout(alerts, h_spacing=Space.L, v_spacing=Space.XS)
        self.over_label = muted_label(over_text(month) if month.over else "")
        if month.over:
            flow.addWidget(self.over_label)
        self.unbudgeted_link = QPushButton(unbudgeted_text(month) + " ›")
        self.unbudgeted_link.setObjectName("LinkButton")
        self.unbudgeted_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.unbudgeted_link.setToolTip(_("Ver las categorías sin presupuesto"))
        self.unbudgeted_link.clicked.connect(self._show_unbudgeted)
        if month.unbudgeted:
            flow.addWidget(self.unbudgeted_link)
        if flow.count():
            card.body.addSpacing(Space.XS)
            card.body.addWidget(alerts)
        if month.unconverted:
            note = hint_label(unconverted_note(month.unconverted))
            card.body.addWidget(note)
        return card

    def _show_unbudgeted(self) -> None:
        """«Sin presupuesto», which the header's warning points to: brought up and lit."""
        if self.unbudgeted_card is not None:
            bring_into_view(self.unbudgeted_card)

    def _budgets_card(self, month: MonthBudgets) -> Card:
        over = sum(1 for b in month.budgets if b.state is BudgetState.OVER)
        title = _("Presupuestos ({count})").format(count=len(month.budgets))
        if over:
            title += " · " + ngettext("{count} excedido", "{count} excedidos", over).format(
                count=over
            )
        card = Card(title)
        column = row_list()
        card.body.addLayout(column)
        theme = self._theme_manager.theme
        for budget in month.budgets:
            row = BudgetPageRow(budget, theme, self._shown.get(budget.category.id))
            category = budget.category
            row.opened.connect(self.record_requested)
            row.transactions_requested.connect(lambda c=category: self._show_transactions(c))
            row.edit_requested.connect(lambda c=category: self.open_budget_dialog(c))
            row.remove_requested.connect(lambda c=category: self.remove_budget(c))
            column.addWidget(row)
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
