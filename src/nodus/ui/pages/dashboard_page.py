"""Dashboard: how much there is, how the month went and where the money went."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from nodus.database.repositories.transaction_repository import TransactionFilter
from nodus.models.money import Money
from nodus.models.period import Month
from nodus.services.container import Services
from nodus.services.dashboard_service import CategoryTotal, MonthSummary
from nodus.ui.event_bus import EventBus
from nodus.ui.formatting import format_date, format_month
from nodus.ui.navigation import PageId
from nodus.ui.pages.page import Page
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.transaction_list import TransactionListBuilder, TransactionListItem
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.charts import DonutChart, ProportionBar, Segment
from nodus.ui.widgets.color import ColorDot
from nodus.ui.widgets.elided_label import ElidedLabel
from nodus.ui.widgets.money_label import MoneyLabel
from nodus.ui.widgets.month_selector import MonthSelector
from nodus.ui.widgets.net_worth_card import NetWorthCard
from nodus.ui.widgets.style import clear_layout, set_style_property

LATEST_COUNT = 6
# Categories listed beside the donut; the rest are added up as one line.
LEGEND_COUNT = 6
REST_LABEL = "Resto"


def muted_label(text: str) -> QLabel:
    label = QLabel(text)
    set_style_property(label, "muted", True)
    return label


def percent(part: Money, whole: Money) -> str:
    """Share of ``whole``, rounded to a whole percent; "—" when ``whole`` is not positive."""
    if whole.cents <= 0:
        return "—"
    return f"{round(100 * part.cents / whole.cents)} %"


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


class DashboardPage(Page):
    """Net worth, the chosen month's cash flow and expenses by category, and its latest
    movements. Without accounts it shows how to get started instead.
    """

    navigate_requested = Signal(object)  # PageId
    transactions_requested = Signal(object)  # Month

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__("Dashboard")
        self._services = services
        self._theme_manager = theme_manager
        self._builder = TransactionListBuilder(services)
        self.month_selector = MonthSelector()
        self.add_header_widget(self.month_selector)

        container = QWidget()
        self._grid = QGridLayout(container)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(16)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        self.content_layout.addWidget(scroll)

        self.month_selector.month_changed.connect(self.refresh)
        theme_manager.theme_changed.connect(self.refresh)
        for signal in (
            event_bus.accounts_changed,
            event_bus.categories_changed,
            event_bus.transactions_changed,
            event_bus.exchange_rates_changed,
        ):
            signal.connect(self.refresh)

    def refresh(self) -> None:
        clear_layout(self._grid)
        if not self._services.accounts.list_accounts(include_archived=True):
            self.month_selector.hide()
            self._grid.addWidget(self._welcome_card(), 0, 0)
            self._grid.setRowStretch(1, 1)
            return
        self.month_selector.show()
        month = self.month_selector.month()
        summary = self._services.dashboard.month_summary(month)
        net_worth_day = min(month.end, date.today())
        title = (
            "Patrimonio"
            if net_worth_day == date.today()
            else f"Patrimonio al {format_date(net_worth_day)}"
        )
        self._grid.addWidget(NetWorthCard(self._services, net_worth_day, title), 0, 0, 1, 2)
        self._grid.addWidget(self._flow_card(summary), 1, 0)
        self._grid.addWidget(self._expenses_card(summary), 1, 1)
        self._grid.addWidget(self._latest_card(month), 0, 2, 2, 1)
        self._grid.setRowStretch(1, 1)
        for column in range(3):
            self._grid.setColumnStretch(column, 1)

    # Cards

    def _flow_card(self, summary: MonthSummary) -> Card:
        theme = self._theme_manager.theme
        card = Card("Flujo del mes")
        savings = MoneyLabel(summary.savings, highlight_positive=True)
        savings.setObjectName("StatValueLarge")
        savings.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        card.body.addWidget(savings)
        card.body.addWidget(muted_label(f"Ahorro de {format_month(summary.month).lower()}"))
        card.body.addSpacing(8)
        card.body.addWidget(
            ProportionBar(
                theme,
                [
                    Segment(theme.income, summary.income.cents),
                    Segment(theme.expense, summary.expenses.cents),
                ],
            )
        )
        card.body.addSpacing(8)
        self._add_figure_row(card, "Ingresos", MoneyLabel(summary.income, highlight_positive=True))
        self._add_figure_row(card, "Gastos", MoneyLabel(-summary.expenses))
        self._add_figure_row(card, "Ahorrado", QLabel(percent(summary.savings, summary.income)))
        if summary.unconverted:
            note = muted_label(
                f"{summary.unconverted} movimiento(s) en dólares sin cotización para su fecha"
                " no se incluyen. Cárgala en Ajustes."
            )
            note.setWordWrap(True)
            card.body.addWidget(note)
        card.body.addStretch()
        return card

    @staticmethod
    def _add_figure_row(card: Card, caption: str, value: QLabel) -> None:
        row = QHBoxLayout()
        row.addWidget(muted_label(caption))
        row.addStretch()
        value.setObjectName("RowTitle")
        row.addWidget(value)
        card.body.addLayout(row)

    def _expenses_card(self, summary: MonthSummary) -> Card:
        card = Card("Gastos por categoría")
        legend_items = self._legend_items(summary.expenses_by_category)
        donut = DonutChart(self._theme_manager.theme)
        donut.set_data(
            [Segment(color, total.cents) for _name, color, total in legend_items],
            "Total" if legend_items else "Sin gastos",
            summary.expenses.format() if legend_items else "este mes",
        )
        card.body.addWidget(donut, stretch=1)
        for name, color, total in legend_items:
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(ColorDot(color, size=10))
            row.addWidget(ElidedLabel(name), stretch=1)
            row.addWidget(muted_label(percent(total, summary.expenses)))
            amount = QLabel(total.format())
            amount.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(amount)
            card.body.addLayout(row)
        return card

    def _legend_items(self, totals: list[CategoryTotal]) -> list[tuple[str, str, Money]]:
        """(name, color, total) for the largest categories, the rest added up as one item."""
        items = [(t.category.name, t.category.color, t.total) for t in totals[:LEGEND_COUNT]]
        rest = totals[LEGEND_COUNT:]
        if rest:
            rest_total = sum((t.total for t in rest[1:]), rest[0].total)
            items.append((REST_LABEL, self._theme_manager.theme.text_muted, rest_total))
        return items

    def _latest_card(self, month: Month) -> Card:
        card = Card("Últimas transacciones")
        # Extra rows leave room for transfers, whose two legs become one item.
        transactions = self._services.transactions.list_transactions(
            TransactionFilter(start=month.start, end=month.end, limit=LATEST_COUNT * 2)
        )
        items = self._builder.build(transactions)[:LATEST_COUNT]
        if not items:
            card.body.addWidget(muted_label("No hay movimientos este mes."))
        transfer_color = self._theme_manager.theme.text_muted
        for item in items:
            card.body.addWidget(LatestTransactionRow(item, transfer_color))
        card.body.addStretch()
        self.see_all_button = QPushButton("Ver todas")
        self.see_all_button.setObjectName("SecondaryButton")
        self.see_all_button.clicked.connect(lambda: self.transactions_requested.emit(month))
        card.body.addWidget(self.see_all_button)
        return card

    def _welcome_card(self) -> Card:
        card = Card()
        title = QLabel("Te damos la bienvenida a Nodus")
        title.setObjectName("DialogTitle")
        text = muted_label(
            "Para empezar, crea una cuenta por cada lugar donde tengas dinero: el banco, el"
            " efectivo, los ahorros en dólares. Si tienes cuentas en dólares, carga también"
            " la cotización en Ajustes para ver tu patrimonio en las dos monedas. Después,"
            " registra tus movimientos con «Agregar transacción»."
        )
        text.setWordWrap(True)
        self.create_account_button = QPushButton("Crear mi primera cuenta")
        self.create_account_button.setObjectName("PrimaryButton")
        self.create_account_button.clicked.connect(
            lambda: self.navigate_requested.emit(PageId.ACCOUNTS)
        )
        buttons = QHBoxLayout()
        buttons.addWidget(self.create_account_button)
        buttons.addStretch()
        card.body.addWidget(title)
        card.body.addWidget(text)
        card.body.addSpacing(8)
        card.body.addLayout(buttons)
        return card
