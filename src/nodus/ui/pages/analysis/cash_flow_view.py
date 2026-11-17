"""Análisis, Flujo de caja: income, expenses and savings by month."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout

from nodus.models.period import Month, Period, format_month
from nodus.services.container import Services
from nodus.services.reports.analysis_service import CashFlowReport
from nodus.services.reports.dashboard_service import MonthFlow, relative_change
from nodus.ui.navigation import TransactionFocus
from nodus.ui.pages.analysis.common import (
    MONTH,
    VERSUS_PREVIOUS_TEXT,
    AnalysisView,
    ModelIndex,
    chart_card,
)
from nodus.ui.text.formatting import percent
from nodus.ui.text.labels import unconverted_note
from nodus.ui.theme.design import Chart, Space
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card, card_header
from nodus.ui.widgets.change_badge import ChangeBadge
from nodus.ui.widgets.charts.bar_chart import BarChart, flow_bar_groups
from nodus.ui.widgets.figure_tile import FigureTile
from nodus.ui.widgets.money_label import AnimatedMoneyLabel
from nodus.ui.widgets.style import RIGHT_ALIGNED
from nodus.ui.widgets.tables.table import fit_rows, make_link_rows, record_table

# Shown, without a pill, where there is no previous period to compare with.
NO_PREVIOUS_TEXT = "Período anterior: sin datos"
INCOME, EXPENSES, SAVINGS, RATE = range(1, 5)
FLOW_COLUMNS = ["Mes", "Ingresos", "Gastos", "Ahorro", "Tasa de ahorro"]


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

    def rowCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self._months)

    def columnCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(FLOW_COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = 0) -> object:  # noqa: N802
        if orientation is Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return FLOW_COLUMNS[section]
        if role == Qt.ItemDataRole.TextAlignmentRole and section != MONTH:
            return RIGHT_ALIGNED
        return None

    def data(self, index: ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
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
            return RIGHT_ALIGNED
        return None


def months_to_list(months: list[MonthFlow], history: list[Month]) -> list[MonthFlow]:
    """The months of the table: those with a history (the report's ``history``), even if
    empty, since an empty month says something, plus any later one with a movement already
    logged ahead. Months before the first movement or still to come would only be rows of
    zeros."""

    def empty(flow: MonthFlow) -> bool:
        return flow.income.is_zero and flow.expenses.is_zero

    return [flow for flow in months if flow.month in history or not empty(flow)]


class CashFlowView(AnalysisView):
    """Income, expenses, savings and savings rate of the period against the previous one,
    with the bars and the table of each month. A bar or a row opens that month."""

    DESCRIPTION = "Lo que entra contra lo que sale cada mes, y cuánto te queda."

    def __init__(self, services: Services, theme_manager: ThemeManager) -> None:
        super().__init__()
        self._services = services
        self._report: CashFlowReport | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.L)

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
        tiles.setSpacing(Space.L)
        for caption, value, badge in (
            ("Ingresos", self.income_label, self.income_badge),
            ("Gastos", self.expenses_label, self.expenses_badge),
            ("Ahorro", self.savings_label, self.savings_badge),
            ("Tasa de ahorro", self.rate_label, self.rate_badge),
        ):
            badge.setToolTip(badge.toolTip() or VERSUS_PREVIOUS_TEXT)
            tiles.addWidget(FigureTile(caption, value, badge, large=True), stretch=1)
        layout.addLayout(tiles)

        self.chart = BarChart(theme_manager.theme)
        self.chart.setMinimumHeight(Chart.STACKED_MIN_HEIGHT)
        self.chart.clicked.connect(lambda index: self._open_month(self._report.months[index]))
        card, self.empty_label, self.unconverted_label = chart_card("Mes a mes", self.chart)
        layout.addWidget(card)

        table_card = self.table_card = Card()
        card_header(table_card, "Detalle por mes")
        self.model = CashFlowTableModel(theme_manager.theme)
        self.table = record_table(self.model, MONTH)
        make_link_rows(
            self.table,
            lambda row: self._open_month(self.model.month(row)),
            "Ver los movimientos del mes",
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
        self.model.set_months(months_to_list(report.months, report.history))
        fit_rows(self.table)

    def _open_month(self, flow: MonthFlow) -> None:
        self.transactions_requested.emit(TransactionFocus(Period.of_months(flow.month)))

    def _set_theme(self, theme: Theme) -> None:
        self.chart.set_theme(theme)
        self.model.set_theme(theme)
