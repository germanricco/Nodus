"""Análisis, Patrimonio: the net worth at the end of each month."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QVBoxLayout

from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.period import Month, Period, format_month
from nodus.services.container import Services
from nodus.services.reports.net_worth_service import NetWorth, NetWorthPoint
from nodus.ui.pages.analysis.common import MONTH, RIGHT, AnalysisView, ModelIndex
from nodus.ui.text.formatting import format_date
from nodus.ui.text.labels import HELD_IN_LABELS
from nodus.ui.theme.design import Chart, Space
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card, card_header
from nodus.ui.widgets.net_worth_card import (
    CURRENCIES,
    CURRENCY_LABELS,
    NetWorthCard,
    rate_effect_text,
    signed,
)
from nodus.ui.widgets.tables.table import fit_rows, record_table

NO_RATE_TEXT = "sin cotización"


class NetWorthTableModel(QAbstractTableModel):
    """The net worth at each month end: what is held in each currency, the total in the
    chosen currency and how much it moved since the month before.

    Columns: the month, one per currency held, the total and the change.
    """

    def __init__(self, theme: Theme) -> None:
        super().__init__()
        self._points: list[NetWorthPoint] = []
        self._rate_effects: list[Money | None] = []
        self._opening: NetWorth | None = None
        self._currency = Currency.ARS
        self._held: list[Currency] = []
        self._theme = theme

    def set_points(
        self,
        points: list[NetWorthPoint],
        opening: NetWorth | None,
        currency: Currency,
        rate_effects: list[Money | None] | None = None,
    ) -> None:
        """``opening`` is the net worth before the first point, to show its change;
        ``rate_effects``, how much of each point's change comes from the rates."""
        self.beginResetModel()
        self._points, self._opening, self._currency = points, opening, currency
        self._rate_effects = rate_effects or [None] * len(points)
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

    def rowCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self._points)

    def columnCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else self.change_column + 1

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = 0) -> object:  # noqa: N802
        if orientation is Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if section == self.total_column:
                return f"Total en {CURRENCY_LABELS[CURRENCIES.index(self._currency)]}"
            held = [HELD_IN_LABELS[currency] for currency in self._held]
            return ["Mes", *held, "Total", "Variación"][section]
        if role == Qt.ItemDataRole.TextAlignmentRole and section != MONTH:
            return RIGHT
        return None

    def data(self, index: ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
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
        if role == Qt.ItemDataRole.ToolTipRole and is_change:
            return rate_effect_text(self._rate_effects[row], self._previous(row)) or None
        if role == Qt.ItemDataRole.ForegroundRole and is_change and change is not None:
            return QColor(self._theme.amount_color(change))
        if role == Qt.ItemDataRole.TextAlignmentRole and column != MONTH:
            return RIGHT
        return None

    def _change(self, row: int) -> Money | None:
        """The move from the previous point (the opening one for the first row)."""
        current = self._points[row].net_worth.total_in[self._currency]
        previous = self._previous(row)
        if current is None or previous is None:
            return None
        return current - previous

    def _previous(self, row: int) -> Money | None:
        before = self._points[row - 1].net_worth if row else self._opening
        return before.total_in[self._currency] if before else None

    @staticmethod
    def _month_text(day: date) -> str:
        """The month, and the day when the point is not its last one (today)."""
        month = Month.of(day)
        return format_month(month) + ("" if day == month.end else f" · al {format_date(day)}")


class NetWorthView(AnalysisView):
    """The net worth along the period, in pesos or dollars, with its change and split by
    currency, and a table of what there was at each month end."""

    DESCRIPTION = "Cuánto tienes al cierre de cada mes, sumando todas tus cuentas y monedas."

    rate_requested = Signal()

    def __init__(self, services: Services, theme_manager: ThemeManager) -> None:
        super().__init__()
        self._services = services
        self._period: Period | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.L)

        self.card = NetWorthCard(services, theme_manager)
        self.card.chart.setMinimumHeight(Chart.STACKED_MIN_HEIGHT)
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
        currency = self.card.currency()
        points = net_worth.month_ends(self._period, date.today())
        opening_day = self._period.start - timedelta(days=1)
        opening = net_worth.net_worth(opening_day)
        starts = [opening_day, *(point.day for point in points[:-1])]
        effects = [
            net_worth.rate_effect(point, start, currency)
            for point, start in zip(points, starts, strict=False)
        ]
        self.model.set_points(points, opening, currency, effects)
        fit_rows(self.table)
