"""The dashboard cards. Each is built once and updated in place, so its charts and figures
can move from what they showed to the new data instead of being rebuilt."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QEnterEvent, QMouseEvent
from PySide6.QtWidgets import (
    QBoxLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nodus.database.repositories.transaction_repository import TransactionFilter
from nodus.models.budget import Budget
from nodus.models.money import Money
from nodus.models.period import Month, Period, format_month
from nodus.models.recurring_charge import DueStatus, RecurringCharge
from nodus.services.container import Services
from nodus.services.dashboard_service import CategoryTotal, Comparison, MonthFlow, PeriodSummary
from nodus.services.recurring_charge_service import UPCOMING_DAYS
from nodus.ui.formatting import format_date
from nodus.ui.labels import days_left_text, due_label, estimate_text, unconverted_note
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.transaction_list import TransactionListBuilder, TransactionListItem
from nodus.ui.widgets.bar_chart import BarChart, BarGroup
from nodus.ui.widgets.budget_bar import BudgetBar, spent_of_limit
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.change_badge import ChangeBadge
from nodus.ui.widgets.charts import DonutChart, ProportionBar, Segment
from nodus.ui.widgets.color import ColorDot
from nodus.ui.widgets.elided_label import ElidedLabel
from nodus.ui.widgets.money_label import AnimatedMoneyLabel
from nodus.ui.widgets.style import clear_layout, set_style_property

LATEST_COUNT = 6
# With upcoming payments above it, the latest movements card gets shorter, so the right
# column stays as tall as the net worth card beside it.
LATEST_COUNT_BELOW_UPCOMING = 4
# Categories listed beside the donut; the rest are added up as one line.
LEGEND_COUNT = 6
REST_LABEL = "Resto"
# Narrowest legend that shows names, shares and amounts without cutting them much.
LEGEND_MIN_WIDTH = 300
COMPARISON_COUNT = 6
# Upcoming charges listed on the dashboard; the page has them all.
UPCOMING_COUNT = 3
# Budgets on the dashboard, the closest to their limit first; the page has them all.
BUDGETS_COUNT = 4


def muted_label(text: str) -> QLabel:
    label = QLabel(text)
    set_style_property(label, "muted", True)
    return label


def percent(part: Money, whole: Money) -> str:
    """Share of ``whole``, rounded to a whole percent; "—" when ``whole`` is not positive."""
    if whole.cents <= 0:
        return "—"
    return f"{round(100 * part.cents / whole.cents)} %"


def due_status_label(charge: RecurringCharge, today: date) -> QLabel:
    """When the charge is due, red once it is overdue."""
    label = QLabel(due_label(charge.days_until(today)))
    if charge.status(today) is DueStatus.OVERDUE:
        set_style_property(label, "tone", "negative")
    else:
        set_style_property(label, "muted", True)
    return label


def flow_bar_groups(flow: list[MonthFlow], selected: Month | None = None) -> list[BarGroup]:
    """The income and expense bars of each month, with ``selected`` highlighted."""
    return [
        BarGroup(
            month.month.short_name,
            month.income.cents,
            month.expenses.cents,
            format_month(month.month),
            (
                f"Ingresos {month.income.format()}",
                f"Gastos {month.expenses.format()}",
                f"Ahorro {month.savings.format()}",
            ),
            selected=month.month == selected,
        )
        for month in flow
    ]


def card_header(card: Card, title: str) -> QHBoxLayout:
    """A title on the left with room on the right, e.g. for a ``ChangeBadge``."""
    header = QHBoxLayout()
    header.setSpacing(8)
    label = QLabel(title.upper())
    label.setObjectName("CardTitle")
    header.addWidget(label)
    header.addStretch()
    card.body.addLayout(header)
    return header


class CategoryLine(QFrame):
    """A row with a color dot and a category name, then any widgets on the right.

    It lights up under the mouse (or when ``set_highlighted`` says so) and can be clicked,
    so the donut legend and the comparison list lead to the category's transactions.
    """

    hovered = Signal(bool)
    clicked = Signal()

    def __init__(self, color: str, name: str, detail: str = "", clickable: bool = True) -> None:
        super().__init__()
        self.setObjectName("CategoryLine")
        self.name = name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(8)
        layout.addWidget(ColorDot(color, size=10))
        texts = QVBoxLayout()
        texts.setSpacing(0)
        texts.addWidget(ElidedLabel(name))
        if detail:
            detail_label = ElidedLabel(detail)
            set_style_property(detail_label, "muted", True)
            texts.addWidget(detail_label)
        layout.addLayout(texts, stretch=1)
        self._layout = layout
        self._clickable = clickable
        if clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip("Ver sus transacciones")

    def add(self, widget: QWidget) -> QWidget:
        self._layout.addWidget(widget)
        return widget

    def set_highlighted(self, highlighted: bool) -> None:
        set_style_property(self, "highlighted", highlighted)

    def enterEvent(self, event: QEnterEvent) -> None:  # noqa: N802
        super().enterEvent(event)
        self.hovered.emit(True)

    def leaveEvent(self, event) -> None:  # noqa: N802
        super().leaveEvent(event)
        self.hovered.emit(False)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        if self._clickable and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class FigureTile(QFrame):
    """A boxed caption and value, like the Income / Expenses / Saved boxes of the reference,
    optionally with a ``badge`` under the value (e.g. a ``ChangeBadge``)."""

    def __init__(self, caption: str, value: QLabel, badge: QWidget | None = None) -> None:
        super().__init__()
        self.setObjectName("FigureTile")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)
        caption_label = QLabel(caption.upper())
        caption_label.setObjectName("StatCaption")
        value.setObjectName("RowTitle")
        value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.value = value
        layout.addWidget(caption_label)
        layout.addWidget(value)
        if badge is not None:
            layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignLeft)


class LatestTransactionRow(QWidget):
    """A movement in the latest transactions card: what, where, how much and when."""

    def __init__(self, item: TransactionListItem, transfer_color: str) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)
        layout.addWidget(ColorDot(item.category_color or transfer_color, size=10))
        texts = QVBoxLayout()
        texts.setSpacing(0)
        title = ElidedLabel(item.description)
        title.setObjectName("RowTitle")
        subtitle = ElidedLabel(f"{item.category_name} · {item.account_text}")
        set_style_property(subtitle, "muted", True)
        texts.addWidget(title)
        texts.addWidget(subtitle)
        layout.addLayout(texts, stretch=1)
        figures = QVBoxLayout()
        figures.setSpacing(0)
        amount = QLabel(item.amount_text)
        amount.setAlignment(Qt.AlignmentFlag.AlignRight)
        set_style_property(amount, "tone", item.tone)
        day = muted_label(format_date(item.occurred_on))
        day.setAlignment(Qt.AlignmentFlag.AlignRight)
        figures.addWidget(amount)
        figures.addWidget(day)
        layout.addLayout(figures)


class LatestTransactionsCard(Card):
    """The period's most recent movements and a button to see them all."""

    see_all_requested = Signal()

    def __init__(self, services: Services, theme_manager: ThemeManager) -> None:
        super().__init__("Últimas transacciones")
        self._services = services
        self._theme_manager = theme_manager
        self._builder = TransactionListBuilder(services)
        self._rows = QVBoxLayout()
        self._rows.setSpacing(0)
        self.body.addLayout(self._rows)
        self.body.addStretch()
        self.see_all_button = QPushButton("Ver todas")
        self.see_all_button.setObjectName("SecondaryButton")
        self.see_all_button.clicked.connect(self.see_all_requested)
        self.body.addWidget(self.see_all_button)

    def show_period(self, period: Period, count: int = LATEST_COUNT) -> None:
        clear_layout(self._rows)
        # Extra rows leave room for transfers, whose two legs become one item.
        transactions = self._services.transactions.list_transactions(
            TransactionFilter(start=period.start, end=period.end, limit=count * 2)
        )
        items = self._builder.build(transactions)[:count]
        if not items:
            self._rows.addWidget(muted_label("Sin movimientos en el período"))
        transfer_color = self._theme_manager.theme.text_muted
        for item in items:
            self._rows.addWidget(LatestTransactionRow(item, transfer_color))


class UpcomingPaymentRow(QWidget):
    """A charge in the upcoming payments card: name, when it is due, amount and "Pagar"."""

    pay_requested = Signal(object)  # RecurringCharge

    def __init__(self, charge: RecurringCharge, today: date, estimate: str = "") -> None:
        super().__init__()
        self.charge = charge
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        name = QLabel(charge.name)
        name.setObjectName("RowTitle")
        texts.addWidget(name)
        texts.addWidget(due_status_label(charge, today))
        layout.addLayout(texts, stretch=1)
        amounts = QVBoxLayout()
        amounts.setSpacing(0)
        amount = QLabel(charge.amount.format())
        amount.setObjectName("RowAmount")
        amount.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        amounts.addWidget(amount)
        if estimate:  # on a line of its own, so the narrow card keeps its width
            estimate_label = muted_label(estimate)
            estimate_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            amounts.addWidget(estimate_label)
        layout.addLayout(amounts)
        self.pay_button = QPushButton("Pagar")
        self.pay_button.setObjectName("SmallButton")
        self.pay_button.clicked.connect(lambda: self.pay_requested.emit(charge))
        layout.addWidget(self.pay_button)


class UpcomingPaymentsCard(Card):
    """Recurring charges overdue or due in the next days, each with a quick "Pagar"."""

    pay_requested = Signal(object)  # RecurringCharge
    see_all_requested = Signal()

    def __init__(self, services: Services) -> None:
        super().__init__()
        self._services = services
        header = card_header(self, "Próximos pagos")
        self.monthly_label = muted_label("")
        self.monthly_label.setToolTip("Lo que suman tus cargos recurrentes en un mes")
        header.addWidget(self.monthly_label)
        self._rows = QVBoxLayout()
        self._rows.setSpacing(0)
        self.body.addLayout(self._rows)
        # Extra height goes below the rows, keeping the title on top.
        self.body.addStretch()
        self.see_all_button = QPushButton("Ver todos")
        self.see_all_button.setObjectName("SecondaryButton")
        self.see_all_button.clicked.connect(self.see_all_requested)
        self.body.addWidget(self.see_all_button)
        self.rows: list[UpcomingPaymentRow] = []

    def show_data(self, today: date) -> None:
        """Hides the card when there are no active charges."""
        recurring = self._services.recurring
        summary = recurring.summary(today)
        self.setVisible(summary.active > 0)
        self.monthly_label.setText(f"~{summary.monthly.format()}/mes")
        clear_layout(self._rows)
        charges = recurring.upcoming(today)
        self.rows = []
        if not charges:
            self._rows.addWidget(
                muted_label(f"Nada que pagar en los próximos {UPCOMING_DAYS} días")
            )
        for charge in charges[:UPCOMING_COUNT]:
            estimate = self._services.recurring.estimated_payment(charge, today)
            row = UpcomingPaymentRow(charge, today, estimate_text(charge.amount, estimate))
            row.pay_requested.connect(self.pay_requested)
            self._rows.addWidget(row)
            self.rows.append(row)


class BudgetRow(QWidget):
    """A budgeted category with its bar underneath; clicking it opens the category's
    transactions of the month. Callers add details to the right of the name on ``line``."""

    clicked = Signal()

    def __init__(self, budget: Budget, theme: Theme) -> None:
        super().__init__()
        self.budget = budget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 6)
        layout.setSpacing(2)
        self.line = CategoryLine(budget.category.color, budget.category.name)
        self.line.hovered.connect(self.line.set_highlighted)
        self.line.clicked.connect(self.clicked)
        self.bar = BudgetBar(theme, budget)
        bar_row = QHBoxLayout()
        bar_row.setContentsMargins(24, 0, 6, 0)  # under the name, past the color dot
        bar_row.addWidget(self.bar)
        layout.addWidget(self.line)
        layout.addLayout(bar_row)


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
        self._rows = QVBoxLayout()
        self._rows.setSpacing(0)
        self.body.addLayout(self._rows)
        self.body.addStretch()
        self.see_all_button = QPushButton("Ver todos")
        self.see_all_button.setObjectName("SecondaryButton")
        self.see_all_button.clicked.connect(self.see_all_requested)
        self.body.addWidget(self.see_all_button)
        self.rows: list[BudgetRow] = []

    def show_month(self, month: Month, today: date) -> None:
        budgets = self._services.budgets.month_budgets(month, today)
        self.setVisible(bool(budgets.budgets))
        self.when_label.setText(days_left_text(month, today) or format_month(month))
        clear_layout(self._rows)
        self.rows = []
        theme = self._theme_manager.theme
        for budget in budgets.budgets[:BUDGETS_COUNT]:
            row = BudgetRow(budget, theme)
            row.line.add(muted_label(spent_of_limit(budget, compact=True)))
            row.clicked.connect(lambda c=budget.category.id: self.category_clicked.emit(c))
            self._rows.addWidget(row)
            self.rows.append(row)


class CashFlowCard(Card):
    """What was saved in the period, against the previous one, and month by month."""

    def __init__(self, theme_manager: ThemeManager) -> None:
        super().__init__()
        theme = theme_manager.theme
        header = card_header(self, "Flujo de caja")
        self.change_badge = ChangeBadge()
        self.change_badge.setToolTip("Ahorro frente al período anterior")
        header.addWidget(self.change_badge)
        self.savings_label = AnimatedMoneyLabel(highlight_positive=True)
        self.savings_label.setObjectName("StatValueLarge")
        self.savings_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.caption_label = muted_label("")
        self.body.addWidget(self.savings_label)
        self.body.addWidget(self.caption_label)
        self.body.addSpacing(6)
        self.proportion = ProportionBar(theme)
        self.body.addWidget(self.proportion)
        self.body.addSpacing(6)

        self.income_label = AnimatedMoneyLabel(highlight_positive=True, compact_when_narrow=True)
        self.expenses_label = AnimatedMoneyLabel(compact_when_narrow=True)
        self.saved_label = QLabel()
        tiles = QHBoxLayout()
        tiles.setSpacing(8)
        for caption, value in (
            ("Ingresos", self.income_label),
            ("Gastos", self.expenses_label),
            ("Ahorrado", self.saved_label),
        ):
            tiles.addWidget(FigureTile(caption, value), stretch=1)
        self.body.addLayout(tiles)

        self.unconverted_label = muted_label("")
        self.unconverted_label.setWordWrap(True)
        self.body.addWidget(self.unconverted_label)
        trend_title = QLabel("MES A MES")
        trend_title.setObjectName("StatCaption")
        self.body.addSpacing(6)
        self.body.addWidget(trend_title)
        self.chart = BarChart(theme)
        self.body.addWidget(self.chart, stretch=1)
        self._theme = theme
        theme_manager.theme_changed.connect(self._set_theme)

    def show_data(self, comparison: Comparison, flow: list[MonthFlow]) -> None:
        summary = comparison.current
        self.savings_label.set_money(summary.savings)
        self.caption_label.setText(f"Ahorro · {summary.period.label()}")
        self.change_badge.set_change(comparison.savings_change)
        self.proportion.set_segments(
            [
                Segment(self._theme.income, summary.income.cents, "income"),
                Segment(self._theme.expense, summary.expenses.cents, "expenses"),
            ]
        )
        self.income_label.set_money(summary.income)
        self.expenses_label.set_money(-summary.expenses)
        self.saved_label.setText(percent(summary.savings, summary.income))
        self.unconverted_label.setText(unconverted_note(summary.unconverted))
        self.unconverted_label.setVisible(bool(summary.unconverted))
        single_month = len(summary.period.months()) == 1
        self.chart.set_groups(
            flow_bar_groups(flow, summary.period.first_month if single_month else None)
        )

    def _set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.proportion.set_theme(theme)
        self.chart.set_theme(theme)


class ExpensesCard(Card):
    """Where the money went: an interactive ring with its legend.

    Hovering a slice or a legend row highlights both; clicking either emits
    ``category_clicked`` with the category's id.
    """

    category_clicked = Signal(int)

    def __init__(self, theme_manager: ThemeManager) -> None:
        super().__init__()
        self._theme_manager = theme_manager
        header = card_header(self, "Gastos por categoría")
        self.change_badge = ChangeBadge(higher_is_better=False)
        self.change_badge.setToolTip("Gastos frente al período anterior")
        header.addWidget(self.change_badge)
        self.donut = DonutChart(theme_manager.theme)
        self.donut.segment_hovered.connect(self._highlight_row)
        self.donut.segment_clicked.connect(self._click_item)
        self.legend_panel = QWidget()
        self._legend = QVBoxLayout(self.legend_panel)
        self._legend.setContentsMargins(0, 0, 0, 0)
        self._legend.setSpacing(0)
        self._chart_area = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        self._chart_area.setSpacing(16)
        self._chart_area.addWidget(self.donut, stretch=1)
        self._chart_area.addWidget(self.legend_panel)
        self.body.addLayout(self._chart_area, stretch=1)
        self.rows: list[CategoryLine] = []
        self._category_ids: list[int | None] = []
        theme_manager.theme_changed.connect(self.donut.set_theme)

    def show_data(self, summary: PeriodSummary, change: float | None) -> None:
        self.change_badge.set_change(change)
        items = self._legend_items(summary.expenses_by_category)
        self._category_ids = [category_id for category_id, *_rest in items]
        self.donut.set_data(
            [
                Segment(
                    color,
                    total.cents,
                    str(category_id),
                    name,
                    total.format(),
                    percent(total, summary.expenses),
                )
                for category_id, name, color, total in items
            ],
            "Total" if items else "Sin gastos",
            summary.expenses if items else None,
            "en el período",
        )
        clear_layout(self._legend)
        self.rows = []
        for index, (category_id, name, color, total) in enumerate(items):
            row = CategoryLine(color, name, clickable=category_id is not None)
            row.add(muted_label(percent(total, summary.expenses)))
            amount = QLabel(total.format())
            amount.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.add(amount)
            row.hovered.connect(lambda on, i=index: self._hover_row(i, on))
            row.clicked.connect(lambda i=index: self._click_item(i))
            self._legend.addWidget(row)
            self.rows.append(row)

    @property
    def legend_beside(self) -> bool:
        return self._chart_area.direction() is QBoxLayout.Direction.LeftToRight

    def fits_legend_beside(self, width: float) -> bool:
        """Whether a card ``width`` wide can show the legend beside the ring uncut."""
        margins = self.body.contentsMargins()
        room = width - margins.left() - margins.right()
        return room >= self.donut.minimumWidth() + self._chart_area.spacing() + LEGEND_MIN_WIDTH

    def set_legend_beside(self, beside: bool) -> None:
        """The legend to the right of the ring, or below it in narrow cards."""
        if beside == self.legend_beside:
            return
        self._chart_area.setDirection(
            QBoxLayout.Direction.LeftToRight if beside else QBoxLayout.Direction.TopToBottom
        )
        self._chart_area.setAlignment(
            self.legend_panel,
            Qt.AlignmentFlag.AlignVCenter if beside else Qt.AlignmentFlag(0),
        )
        # Beside the ring, the legend keeps room for whole names.
        self.legend_panel.setMinimumWidth(LEGEND_MIN_WIDTH if beside else 0)
        self._chart_area.setStretchFactor(self.legend_panel, 1 if beside else 0)

    def _legend_items(
        self, totals: list[CategoryTotal]
    ) -> list[tuple[int | None, str, str, Money]]:
        """(category id, name, color, total) for the largest categories, the rest added up
        as one item without an id."""
        items: list[tuple[int | None, str, str, Money]] = [
            (t.category.id, t.category.name, t.category.color, t.total)
            for t in totals[:LEGEND_COUNT]
        ]
        rest = totals[LEGEND_COUNT:]
        if rest:
            rest_total = sum((t.total for t in rest[1:]), rest[0].total)
            items.append((None, REST_LABEL, self._theme_manager.theme.text_muted, rest_total))
        return items

    def _hover_row(self, index: int, on: bool) -> None:
        self.donut.set_highlight(index if on else None)
        self._highlight_row(index if on else -1)

    def _highlight_row(self, index: int) -> None:
        for i, row in enumerate(self.rows):
            row.set_highlighted(i == index)

    def _click_item(self, index: int) -> None:
        category_id = self._category_ids[index] if index < len(self._category_ids) else None
        if category_id is not None:
            self.category_clicked.emit(category_id)


class ComparisonCard(Card):
    """The categories with the most spending, each against the previous period."""

    category_clicked = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        card_header(self, "Frente al período anterior")
        self._rows = QVBoxLayout()
        self._rows.setSpacing(2)
        self.body.addLayout(self._rows)
        self.body.addStretch()
        self.rows: list[CategoryLine] = []

    def show_data(self, comparison: Comparison) -> None:
        clear_layout(self._rows)
        self.rows = []
        changes = comparison.categories[:COMPARISON_COUNT]
        if not changes:
            self._rows.addWidget(muted_label("Sin gastos en el período"))
        for change in changes:
            row = CategoryLine(change.category.color, change.category.name, change.current.format())
            badge = ChangeBadge(higher_is_better=False, none_text="Nueva")
            # In the row before set_change shows it, or it would flash as its own window.
            row.add(badge)
            badge.set_change(change.change)
            badge.setToolTip(f"Período anterior: {change.previous.format()}")
            badge.setMinimumWidth(64)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.clicked.connect(lambda c=change.category.id: self.category_clicked.emit(c))
            row.hovered.connect(lambda on, r=row: r.set_highlighted(on))
            self._rows.addWidget(row)
            self.rows.append(row)
