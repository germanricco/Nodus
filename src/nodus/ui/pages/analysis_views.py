"""The reports of the analysis page. Each view shows one report for a period it is given
and asks for transactions through ``transactions_requested``."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.period import Month, Period, format_month
from nodus.services.analysis_service import CashFlowReport, Metric, MonthTrend, Trends
from nodus.services.container import Services
from nodus.services.dashboard_service import (
    SUMMARY_CURRENCY,
    CategoryTotal,
    MonthFlow,
    relative_change,
)
from nodus.services.net_worth_service import NetWorth, NetWorthPoint
from nodus.ui.formatting import format_date
from nodus.ui.labels import HELD_IN_LABELS, movements_text, unconverted_note
from nodus.ui.navigation import TransactionFocus
from nodus.ui.pages.dashboard_cards import (
    CategoryLine,
    FigureTile,
    card_header,
    flow_bar_groups,
    muted_label,
    percent,
)
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.bar_chart import BarChart
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.change_badge import ChangeBadge
from nodus.ui.widgets.chart_base import format_compact
from nodus.ui.widgets.money_label import AnimatedMoneyLabel
from nodus.ui.widgets.net_worth_card import CURRENCIES, CURRENCY_LABELS, NetWorthCard, signed
from nodus.ui.widgets.segmented import SegmentedControl
from nodus.ui.widgets.stacked_bar_chart import StackedBar, StackedBarChart, StackSegment
from nodus.ui.widgets.style import clear_layout
from nodus.ui.widgets.table import fit_rows, record_table

METRICS = list(Metric)
# Categories stacked in the bars, the largest of the period; the rest share one piece.
STACKED_CATEGORIES = 7
REST_LABEL = "Resto"
# Payees listed; the rest are left to the transactions page.
PAYEES_SHOWN = 8
NO_PAYEE_LABEL = "Sin beneficiario"
TAGS_HINT = "Un movimiento con varias etiquetas suma en cada una."
TOOLTIP_CATEGORIES = 3
EMPTY_TEXT = "Sin movimientos en el período"
# Shown, without a pill, where there is no previous period to compare with.
NO_PREVIOUS_TEXT = "—"

MONTH, INCOME, EXPENSES, SAVINGS, RATE = range(5)
FLOW_COLUMNS = ["Mes", "Ingresos", "Gastos", "Ahorro", "Tasa de ahorro"]
NO_RATE_TEXT = "sin cotización"

_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
_ModelIndex = QModelIndex | QPersistentModelIndex


def amount_label(money: Money) -> QLabel:
    label = QLabel(money.format())
    label.setAlignment(_RIGHT)
    return label


def chart_card(title: str, chart: QWidget) -> tuple[Card, QLabel, QLabel]:
    """A card with ``chart``, the label shown instead of it when the period is empty and
    the note about movements left out for lack of an exchange rate."""
    card = Card()
    card_header(card, title)
    empty_label = muted_label(EMPTY_TEXT)
    empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    unconverted_label = muted_label("")
    unconverted_label.setWordWrap(True)
    card.body.addWidget(chart, stretch=1)
    card.body.addWidget(empty_label)
    card.body.addWidget(unconverted_label)
    return card, empty_label, unconverted_label


def rows_card(title: str) -> tuple[Card, QVBoxLayout]:
    """A card with ``title`` and a column of rows to fill, as the breakdowns use."""
    card = Card()
    card_header(card, title)
    rows = QVBoxLayout()
    rows.setSpacing(0)
    card.body.addLayout(rows)
    card.body.addStretch()
    return card, rows


class AnalysisView(QWidget):
    """A report: shows a period and asks for the transactions behind its figures."""

    transactions_requested = Signal(object)  # TransactionFocus

    def show_period(self, period: Period) -> None:
        raise NotImplementedError


class TrendsView(AnalysisView):
    """Expenses, income or savings month by month: totals against the previous period,
    bars stacked by category with the monthly average, and the split by category, by
    payee and by tag. Clicking a bar, a piece or a row opens those transactions."""

    def __init__(self, services: Services, theme_manager: ThemeManager) -> None:
        super().__init__()
        self._services = services
        self._theme = theme_manager.theme
        self._trends: Trends | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.metric_input = SegmentedControl([metric.value for metric in METRICS])
        metric_row = QHBoxLayout()
        metric_row.addWidget(self.metric_input)
        metric_row.addStretch()
        layout.addLayout(metric_row)

        self.total_label = AnimatedMoneyLabel()
        self.change_badge = ChangeBadge(none_text=NO_PREVIOUS_TEXT)
        self.change_badge.setToolTip("Frente al período anterior, del mismo largo")
        self.previous_label = QLabel()
        self.average_label = QLabel()
        self.total_tile = FigureTile("Total", self.total_label, self.change_badge, large=True)
        self.previous_tile = FigureTile("Período anterior", self.previous_label, large=True)
        tiles = QHBoxLayout()
        tiles.setSpacing(16)
        for tile in (self.total_tile, self.previous_tile,
                     FigureTile("Promedio mensual", self.average_label, large=True)):  # fmt: skip
            tiles.addWidget(tile, stretch=1)
        layout.addLayout(tiles)

        self.chart = StackedBarChart(
            self._theme, lambda cents: format_compact(cents, SUMMARY_CURRENCY)
        )
        self.chart.clicked.connect(self._bar_clicked)
        card, self.empty_label, self.unconverted_label = chart_card("Mes a mes", self.chart)
        layout.addWidget(card)

        self.categories_card, self._category_rows = rows_card("Por categoría")
        self.payees_card, self._payee_rows = rows_card("Por beneficiario")
        breakdown = QHBoxLayout()
        breakdown.setSpacing(16)
        breakdown.addWidget(self.categories_card, stretch=1)
        breakdown.addWidget(self.payees_card, stretch=1)
        layout.addLayout(breakdown)
        self.tags_card, self._tag_rows = rows_card("Por etiqueta")
        self.tags_card.setToolTip(TAGS_HINT)
        layout.addWidget(self.tags_card)
        layout.addStretch()

        self.metric_input.changed.connect(lambda _index: self._reload())
        theme_manager.theme_changed.connect(self._set_theme)

    @property
    def metric(self) -> Metric:
        return METRICS[self.metric_input.index()]

    def show_period(self, period: Period) -> None:
        self._period = period
        self._reload()

    def _reload(self) -> None:
        trends = self._trends = self._services.analysis.trends(self._period, self.metric)
        expenses = trends.metric is Metric.EXPENSES
        self.total_label.set_money(trends.total)
        # More spending is bad news; more income or savings is good news.
        self.change_badge.set_higher_is_better(not expenses)
        self.change_badge.set_change(trends.change)
        self.previous_label.setText(trends.previous_total.format())
        self.average_label.setText(trends.average.format())

        has_data = any(not month.total.is_zero for month in trends.months)
        self.chart.setVisible(has_data)
        self.empty_label.setVisible(not has_data)
        stacked = self._stacked_categories(trends.categories)
        self.chart.set_bars(
            [self._bar(month, stacked) for month in trends.months],
            trends.average.cents if has_data else None,
        )
        self.unconverted_label.setText(unconverted_note(trends.unconverted))
        self.unconverted_label.setVisible(bool(trends.unconverted))

        breakdown = trends.metric is not Metric.SAVINGS
        self.categories_card.setVisible(breakdown)
        self.payees_card.setVisible(breakdown)
        self.tags_card.setVisible(breakdown and bool(trends.tags))
        if breakdown:
            self._fill_categories(trends)
            self._fill_payees(trends)
            self._fill_tags(trends)

    # Bars

    def _stacked_categories(self, categories: list[CategoryTotal]) -> list[int]:
        return [total.category.id for total in categories[:STACKED_CATEGORIES]]

    def _bar(self, month: MonthTrend, stacked: list[int]) -> StackedBar:
        title = format_month(month.month)
        if self.metric is Metric.SAVINGS:
            color = self._theme.income if not month.total.is_negative else self._theme.expense
            segments = (StackSegment(None, color, month.total.cents),)
            return StackedBar(month.month.short_name, segments, title,
                              (f"Ahorro {month.total.format()}",), month.month)  # fmt: skip
        by_id = {total.category.id: total for total in month.by_category}
        segments = [
            StackSegment(category_id, by_id[category_id].category.color,
                         by_id[category_id].total.cents)
            for category_id in stacked
            if category_id in by_id
        ]  # fmt: skip
        rest = sum(t.total.cents for t in month.by_category if t.category.id not in stacked)
        if rest:
            segments.append(StackSegment(None, self._theme.text_muted, rest))
        lines = [f"Total {month.total.format()}"] + [
            f"{total.category.name} {total.total.format()}"
            for total in month.by_category[:TOOLTIP_CATEGORIES]
        ]
        return StackedBar(month.month.short_name, tuple(segments), title, tuple(lines), month.month)

    def _bar_clicked(self, index: int, category_id: int | None) -> None:
        month = self._trends.months[index].month
        self.transactions_requested.emit(TransactionFocus(Period.of_months(month), category_id))

    # Breakdown

    def _fill_categories(self, trends: Trends) -> None:
        clear_layout(self._category_rows)
        if not trends.categories:
            self._category_rows.addWidget(muted_label(EMPTY_TEXT))
        for total in trends.categories:
            row = CategoryLine(total.category.color, total.category.name)
            row.add(muted_label(percent(total.total, trends.total)))
            row.add(amount_label(total.total))
            row.clicked.connect(
                lambda category_id=total.category.id: self.transactions_requested.emit(
                    TransactionFocus(self._period, category_id=category_id)
                )
            )
            self._category_rows.addWidget(row)

    def _fill_payees(self, trends: Trends) -> None:
        clear_layout(self._payee_rows)
        named = [p for p in trends.payees if p.payee is not None][:PAYEES_SHOWN]
        without = [p for p in trends.payees if p.payee is None]
        if not trends.payees:
            self._payee_rows.addWidget(muted_label(EMPTY_TEXT))
        for total in named + without:
            name = total.payee.name if total.payee else NO_PAYEE_LABEL
            color = self._theme.accent if total.payee else self._theme.border
            row = CategoryLine(color, name, movements_text(total.count),
                               clickable=total.payee is not None)  # fmt: skip
            row.add(muted_label(percent(total.total, trends.total)))
            row.add(amount_label(total.total))
            if total.payee is not None:
                row.clicked.connect(
                    lambda payee_id=total.payee.id: self.transactions_requested.emit(
                        TransactionFocus(self._period, payee_id=payee_id)
                    )
                )
            self._payee_rows.addWidget(row)

    def _fill_tags(self, trends: Trends) -> None:
        clear_layout(self._tag_rows)
        for total in trends.tags:
            row = CategoryLine(total.tag.color, total.tag.name, movements_text(total.count))
            row.add(muted_label(percent(total.total, trends.total)))
            row.add(amount_label(total.total))
            row.clicked.connect(
                lambda tag_id=total.tag.id: self.transactions_requested.emit(
                    TransactionFocus(self._period, tag_id=tag_id)
                )
            )
            self._tag_rows.addWidget(row)

    def _set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.chart.set_theme(theme)
        if self._trends is not None:
            self._reload()


class CashFlowTableModel(QAbstractTableModel):
    """Income, expenses, savings and savings rate of each month, amounts in their colors."""

    def __init__(self, theme: Theme) -> None:
        super().__init__()
        self._months: list[MonthFlow] = []
        self._theme = theme

    def set_months(self, months: list[MonthFlow]) -> None:
        self.beginResetModel()
        self._months = months
        self.endResetModel()

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        if self._months:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._months) - 1, RATE))

    def month(self, row: int) -> MonthFlow:
        return self._months[row]

    def rowCount(self, parent: _ModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self._months)

    def columnCount(self, parent: _ModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(FLOW_COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = 0) -> object:  # noqa: N802
        if orientation is Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return FLOW_COLUMNS[section]
        if role == Qt.ItemDataRole.TextAlignmentRole and section != MONTH:
            return _RIGHT
        return None

    def data(self, index: _ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        flow = self._months[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return [
                format_month(flow.month),
                flow.income.format(),
                flow.expenses.format(),
                flow.savings.format(),
                percent(flow.savings, flow.income),
            ][column]
        if role == Qt.ItemDataRole.ForegroundRole and column in (INCOME, EXPENSES, SAVINGS):
            amount = [flow.income, -flow.expenses, flow.savings][column - INCOME]
            return QColor(self._theme.amount_color(amount))
        if role == Qt.ItemDataRole.TextAlignmentRole and column != MONTH:
            return _RIGHT
        return None


def months_to_list(months: list[MonthFlow], current: Month) -> list[MonthFlow]:
    """The months of the table, without the empty ones before the first movement or still
    to come (a year that has not ended), which would only be rows of zeros. An empty month
    in between stays: it says something."""

    def empty(flow: MonthFlow) -> bool:
        return flow.income.is_zero and flow.expenses.is_zero

    first = next((i for i, flow in enumerate(months) if not empty(flow)), len(months))
    return [flow for flow in months[first:] if flow.month <= current or not empty(flow)]


class CashFlowView(AnalysisView):
    """Income, expenses, savings and savings rate of the period against the previous one,
    with the bars and the table of each month. A bar or a row opens that month."""

    def __init__(self, services: Services, theme_manager: ThemeManager) -> None:
        super().__init__()
        self._services = services
        self._report: CashFlowReport | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.income_label = AnimatedMoneyLabel(highlight_positive=True)
        self.expenses_label = AnimatedMoneyLabel()
        self.savings_label = AnimatedMoneyLabel(highlight_positive=True)
        self.rate_label = QLabel()
        self.income_badge = ChangeBadge(none_text=NO_PREVIOUS_TEXT)
        self.expenses_badge = ChangeBadge(higher_is_better=False, none_text=NO_PREVIOUS_TEXT)
        self.savings_badge = ChangeBadge(none_text=NO_PREVIOUS_TEXT)
        self.rate_badge = ChangeBadge(none_text=NO_PREVIOUS_TEXT, unit="pp")
        self.rate_badge.setToolTip("Diferencia en puntos porcentuales")
        tiles = QHBoxLayout()
        tiles.setSpacing(16)
        for caption, value, badge in (
            ("Ingresos", self.income_label, self.income_badge),
            ("Gastos", self.expenses_label, self.expenses_badge),
            ("Ahorro", self.savings_label, self.savings_badge),
            ("Tasa de ahorro", self.rate_label, self.rate_badge),
        ):
            badge.setToolTip(badge.toolTip() or "Frente al período anterior, del mismo largo")
            tiles.addWidget(FigureTile(caption, value, badge, large=True), stretch=1)
        layout.addLayout(tiles)

        self.chart = BarChart(theme_manager.theme)
        self.chart.setMinimumHeight(StackedBarChart.MIN_HEIGHT)
        self.chart.clicked.connect(lambda index: self._open_month(self._report.months[index]))
        card, self.empty_label, self.unconverted_label = chart_card("Mes a mes", self.chart)
        layout.addWidget(card)

        table_card = self.table_card = Card()
        card_header(table_card, "Detalle por mes")
        self.model = CashFlowTableModel(theme_manager.theme)
        self.table = record_table(self.model, MONTH)
        self.table.setToolTip("Doble clic para ver los movimientos del mes")
        self.table.doubleClicked.connect(
            lambda index: self._open_month(self.model.month(index.row()))
        )
        table_card.body.addWidget(self.table)
        layout.addWidget(table_card)
        layout.addStretch()

        theme_manager.theme_changed.connect(self._set_theme)

    def show_period(self, period: Period) -> None:
        report = self._report = self._services.analysis.cash_flow(period)
        current, previous = report.current, report.previous
        self.income_label.set_money(current.income)
        self.expenses_label.set_money(-current.expenses)
        self.savings_label.set_money(current.savings)
        self.rate_label.setText(percent(current.savings, current.income))
        self.income_badge.set_change(relative_change(current.income, previous.income))
        self.expenses_badge.set_change(relative_change(current.expenses, previous.expenses))
        self.savings_badge.set_change(relative_change(current.savings, previous.savings))
        rates = (current.savings_rate, previous.savings_rate)
        self.rate_badge.set_change(None if None in rates else rates[0] - rates[1])

        has_data = not (current.income.is_zero and current.expenses.is_zero)
        self.chart.setVisible(has_data)
        self.empty_label.setVisible(not has_data)
        self.table_card.setVisible(has_data)  # it would be a table without rows
        self.chart.set_groups(flow_bar_groups(report.months))
        self.unconverted_label.setText(unconverted_note(report.unconverted))
        self.unconverted_label.setVisible(bool(report.unconverted))
        self.model.set_months(months_to_list(report.months, Month.of(date.today())))
        fit_rows(self.table)

    def _open_month(self, flow: MonthFlow) -> None:
        self.transactions_requested.emit(TransactionFocus(Period.of_months(flow.month)))

    def _set_theme(self, theme: Theme) -> None:
        self.chart.set_theme(theme)
        self.model.set_theme(theme)


class NetWorthTableModel(QAbstractTableModel):
    """The net worth at each month end: what is held in each currency, the total in the
    chosen currency and how much it moved since the month before.

    Columns: the month, one per currency held, the total and the change.
    """

    def __init__(self, theme: Theme) -> None:
        super().__init__()
        self._points: list[NetWorthPoint] = []
        self._opening: NetWorth | None = None
        self._currency = Currency.ARS
        self._held: list[Currency] = []
        self._theme = theme

    def set_points(
        self, points: list[NetWorthPoint], opening: NetWorth | None, currency: Currency
    ) -> None:
        """``opening`` is the net worth before the first point, to show its change."""
        self.beginResetModel()
        self._points, self._opening, self._currency = points, opening, currency
        self._held = list(points[0].net_worth.by_currency) if points else []
        self.endResetModel()

    @property
    def total_column(self) -> int:
        return 1 + len(self._held)

    @property
    def change_column(self) -> int:
        return self.total_column + 1

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        if self._points:
            last = self.index(len(self._points) - 1, self.change_column)
            self.dataChanged.emit(self.index(0, 0), last)

    def rowCount(self, parent: _ModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self._points)

    def columnCount(self, parent: _ModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else self.change_column + 1

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = 0) -> object:  # noqa: N802
        if orientation is Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if section == self.total_column:
                return f"Total en {CURRENCY_LABELS[CURRENCIES.index(self._currency)]}"
            held = [HELD_IN_LABELS[currency] for currency in self._held]
            return ["Mes", *held, "Total", "Variación"][section]
        if role == Qt.ItemDataRole.TextAlignmentRole and section != MONTH:
            return _RIGHT
        return None

    def data(self, index: _ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        row, column = index.row(), index.column()
        point = self._points[row]
        change = self._change(row)
        if role == Qt.ItemDataRole.DisplayRole:
            by_currency = point.net_worth.by_currency
            total = point.net_worth.total_in[self._currency]
            return [
                self._month_text(point.day),
                *(by_currency[currency].format() for currency in self._held),
                total.format() if total is not None else NO_RATE_TEXT,
                signed(change) if change is not None else "—",
            ][column]
        is_change = column == self.change_column
        if role == Qt.ItemDataRole.ForegroundRole and is_change and change is not None:
            return QColor(self._theme.amount_color(change))
        if role == Qt.ItemDataRole.TextAlignmentRole and column != MONTH:
            return _RIGHT
        return None

    def _change(self, row: int) -> Money | None:
        """The move from the previous point (the opening one for the first row)."""
        before = self._points[row - 1].net_worth if row else self._opening
        current = self._points[row].net_worth.total_in[self._currency]
        previous = before.total_in[self._currency] if before else None
        if current is None or previous is None:
            return None
        return current - previous

    @staticmethod
    def _month_text(day: date) -> str:
        """The month, and the day when the point is not its last one (today)."""
        month = Month.of(day)
        return format_month(month) + ("" if day == month.end else f" · al {format_date(day)}")


class NetWorthView(AnalysisView):
    """The net worth along the period, in pesos or dollars, with its change and split by
    currency, and a table of what there was at each month end."""

    rate_requested = Signal()

    def __init__(self, services: Services, theme_manager: ThemeManager) -> None:
        super().__init__()
        self._services = services
        self._period: Period | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.card = NetWorthCard(services, theme_manager)
        self.card.chart.setMinimumHeight(StackedBarChart.MIN_HEIGHT)
        self.card.rate_requested.connect(self.rate_requested)
        self.card.currency_input.changed.connect(lambda _index: self._fill_table())
        layout.addWidget(self.card)

        table_card = Card()
        card_header(table_card, "Fin de cada mes")
        self.model = NetWorthTableModel(theme_manager.theme)
        self.table = record_table(self.model, MONTH)
        table_card.body.addWidget(self.table)
        layout.addWidget(table_card)
        layout.addStretch()

        theme_manager.theme_changed.connect(self.model.set_theme)

    def show_period(self, period: Period) -> None:
        self._period = period
        self.card.show_day(min(period.end, date.today()), period)
        self._fill_table()

    def _fill_table(self) -> None:
        if self._period is None:
            return
        net_worth = self._services.net_worth
        points = net_worth.month_ends(self._period, date.today())
        opening = net_worth.net_worth(self._period.start - timedelta(days=1))
        self.model.set_points(points, opening, self.card.currency())
        fit_rows(self.table)
