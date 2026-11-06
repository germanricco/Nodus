"""The reports of the analysis page. Each view shows one report for a period it is given
and asks for transactions through ``transactions_requested``."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from nodus.models.money import Money
from nodus.models.period import Period, format_month
from nodus.services.analysis_service import Metric, MonthTrend, Trends
from nodus.services.container import Services
from nodus.services.dashboard_service import SUMMARY_CURRENCY, CategoryTotal
from nodus.ui.labels import movements_text, unconverted_note
from nodus.ui.pages.dashboard_cards import (
    CategoryLine,
    FigureTile,
    card_header,
    muted_label,
    percent,
)
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.change_badge import ChangeBadge
from nodus.ui.widgets.chart_base import format_compact
from nodus.ui.widgets.money_label import AnimatedMoneyLabel
from nodus.ui.widgets.segmented import SegmentedControl
from nodus.ui.widgets.stacked_bar_chart import StackedBar, StackedBarChart, StackSegment
from nodus.ui.widgets.style import clear_layout

METRICS = list(Metric)
# Categories stacked in the bars, the largest of the period; the rest share one piece.
STACKED_CATEGORIES = 7
REST_LABEL = "Resto"
# Payees listed; the rest are left to the transactions page.
PAYEES_SHOWN = 8
NO_PAYEE_LABEL = "Sin beneficiario"
TOOLTIP_CATEGORIES = 3


def amount_label(money: Money) -> QLabel:
    label = QLabel(money.format())
    label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return label


class AnalysisView(QWidget):
    """A report: shows a period and asks for the transactions behind its figures."""

    transactions_requested = Signal(object, object, object)  # Period, category id, payee id

    def show_period(self, period: Period) -> None:
        raise NotImplementedError


class TrendsView(AnalysisView):
    """Expenses, income or savings month by month: totals against the previous period,
    bars stacked by category with the monthly average, and the split by category and
    by payee. Clicking a bar, a piece or a row opens those transactions."""

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
        self.change_badge = ChangeBadge(none_text="Sin datos del período anterior")
        self.change_badge.setToolTip("Frente al período anterior, del mismo largo")
        self.previous_label = QLabel()
        self.average_label = QLabel()
        self.total_tile = FigureTile("Total", self.total_label, self.change_badge)
        self.previous_tile = FigureTile("Período anterior", self.previous_label)
        tiles = QHBoxLayout()
        tiles.setSpacing(16)
        for tile in (self.total_tile, self.previous_tile,
                     FigureTile("Promedio mensual", self.average_label)):  # fmt: skip
            tiles.addWidget(tile, stretch=1)
        layout.addLayout(tiles)

        chart_card = Card()
        self.chart_title = card_header(chart_card, "Mes a mes")
        self.chart = StackedBarChart(
            self._theme, lambda cents: format_compact(cents, SUMMARY_CURRENCY)
        )
        self.chart.clicked.connect(self._bar_clicked)
        self.empty_label = muted_label("Sin movimientos en el período")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.unconverted_label = muted_label("")
        self.unconverted_label.setWordWrap(True)
        chart_card.body.addWidget(self.chart, stretch=1)
        chart_card.body.addWidget(self.empty_label)
        chart_card.body.addWidget(self.unconverted_label)
        layout.addWidget(chart_card)

        self.categories_card = Card()
        card_header(self.categories_card, "Por categoría")
        self._category_rows = QVBoxLayout()
        self._category_rows.setSpacing(0)
        self.categories_card.body.addLayout(self._category_rows)
        self.categories_card.body.addStretch()
        self.payees_card = Card()
        card_header(self.payees_card, "Por beneficiario")
        self._payee_rows = QVBoxLayout()
        self._payee_rows.setSpacing(0)
        self.payees_card.body.addLayout(self._payee_rows)
        self.payees_card.body.addStretch()
        breakdown = QHBoxLayout()
        breakdown.setSpacing(16)
        breakdown.addWidget(self.categories_card, stretch=1)
        breakdown.addWidget(self.payees_card, stretch=1)
        layout.addLayout(breakdown)
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
        if breakdown:
            self._fill_categories(trends)
            self._fill_payees(trends)

    # Bars

    def _stacked_categories(self, categories: list[CategoryTotal]) -> list[int]:
        return [total.category.id for total in categories[:STACKED_CATEGORIES]]

    def _bar(self, month: MonthTrend, stacked: list[int]) -> StackedBar:
        title = format_month(month.month)
        if self.metric is Metric.SAVINGS:
            color = self._theme.income if not month.total.is_negative else self._theme.expense
            segments = (StackSegment(None, color, month.total.cents),)
            return StackedBar(month.month.short_name, segments, title,
                              (f"Ahorro {month.total.format()}",))  # fmt: skip
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
        return StackedBar(month.month.short_name, tuple(segments), title, tuple(lines))

    def _bar_clicked(self, index: int, category_id: int | None) -> None:
        month = self._trends.months[index].month
        self.transactions_requested.emit(Period.of_months(month), category_id, None)

    # Breakdown

    def _fill_categories(self, trends: Trends) -> None:
        clear_layout(self._category_rows)
        if not trends.categories:
            self._category_rows.addWidget(muted_label("Sin movimientos en el período"))
        for total in trends.categories:
            row = CategoryLine(total.category.color, total.category.name)
            row.add(muted_label(percent(total.total, trends.total)))
            row.add(amount_label(total.total))
            row.clicked.connect(
                lambda category_id=total.category.id: self.transactions_requested.emit(
                    self._period, category_id, None
                )
            )
            self._category_rows.addWidget(row)

    def _fill_payees(self, trends: Trends) -> None:
        clear_layout(self._payee_rows)
        named = [p for p in trends.payees if p.payee is not None][:PAYEES_SHOWN]
        without = [p for p in trends.payees if p.payee is None]
        if not trends.payees:
            self._payee_rows.addWidget(muted_label("Sin movimientos en el período"))
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
                        self._period, None, payee_id
                    )
                )
            self._payee_rows.addWidget(row)

    def _set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.chart.set_theme(theme)
        if self._trends is not None:
            self._reload()
