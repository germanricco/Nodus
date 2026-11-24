"""Análisis, Tendencias: a metric month by month and its breakdowns."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout

from nodus.i18n import N_, _
from nodus.models.period import Period, format_month
from nodus.services.container import Services
from nodus.services.reports.analysis_service import Metric, MonthTrend, Trends
from nodus.services.reports.dashboard_service import CategoryTotal
from nodus.ui.navigation import RecordLink, TransactionFocus
from nodus.ui.pages.analysis.common import VERSUS_PREVIOUS_TEXT, AnalysisView, chart_card, rows_card
from nodus.ui.text.formatting import percent
from nodus.ui.text.labels import movements_text, unconverted_note
from nodus.ui.theme.design import Space
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card_grid import CardGrid
from nodus.ui.widgets.change_badge import ChangeBadge
from nodus.ui.widgets.charts.chart_base import compact_pesos
from nodus.ui.widgets.charts.stacked_bar_chart import StackedBar, StackedBarChart, StackSegment
from nodus.ui.widgets.empty_state import NO_MOVEMENTS_TEXT, EmptyState
from nodus.ui.widgets.figure_row import FigureRow
from nodus.ui.widgets.figure_tile import FigureTile
from nodus.ui.widgets.inputs.segmented import SegmentedControl
from nodus.ui.widgets.money_label import AnimatedMoneyLabel
from nodus.ui.widgets.style import amount_label, clear_layout, muted_label
from nodus.ui.widgets.tables.category_line import CategoryLine

METRICS = list(Metric)
# Categories stacked in the bars, the largest of the period; the rest share one piece.
STACKED_CATEGORIES = 7
# Payees listed; the rest are left to the transactions page.
PAYEES_SHOWN = 8
NO_PAYEE_LABEL = N_("Sin beneficiario")
TAGS_HINT = N_("Un movimiento con varias etiquetas suma en cada una.")
TOOLTIP_CATEGORIES = 3


class TrendsView(AnalysisView):
    """Expenses, income or savings month by month: totals against the previous period,
    bars stacked by category with the monthly average, and the split by category, by
    payee and by tag. Clicking a bar, a piece or a row opens those transactions."""

    DESCRIPTION = N_("Lo que gastas, ganas y ahorras mes a mes, frente al período anterior.")

    def __init__(self, services: Services, theme_manager: ThemeManager) -> None:
        super().__init__()
        self._services = services
        self._theme = theme_manager.theme
        self._trends: Trends | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.L)

        self.metric_input = SegmentedControl([metric.label for metric in METRICS])
        metric_row = QHBoxLayout()
        metric_row.addWidget(self.metric_input)
        metric_row.addStretch()
        layout.addLayout(metric_row)

        self.total_label = AnimatedMoneyLabel()
        # Without a previous period the badge steps aside: its tile already says so.
        self.change_badge = ChangeBadge()
        self.change_badge.setToolTip(_(VERSUS_PREVIOUS_TEXT))
        self.previous_label = QLabel()
        self.average_label = QLabel()
        self.total_tile = FigureTile(_("Total"), self.total_label, self.change_badge)
        self.previous_tile = FigureTile(_("Período anterior"), self.previous_label)
        self.figures = FigureRow()
        average_tile = FigureTile(_("Promedio mensual"), self.average_label)
        for tile in (self.total_tile, self.previous_tile, average_tile):
            self.figures.add_tile(tile)
        layout.addWidget(self.figures)

        self.chart = StackedBarChart(self._theme, compact_pesos)
        self.chart.clicked.connect(self._bar_clicked)
        card, self.empty_label, self.unconverted_label = chart_card(_("Mes a mes"), self.chart)
        layout.addWidget(card)

        self.categories_card, self._category_rows = rows_card(_("Por categoría"))
        self.payees_card, self._payee_rows = rows_card(_("Por beneficiario"))
        # Side by side while both fit, one under the other in a narrow window.
        self.breakdown = CardGrid()
        self.breakdown.set_cards([self.categories_card, self.payees_card])
        layout.addWidget(self.breakdown)
        self.tags_card, self._tag_rows = rows_card(_("Por etiqueta"))
        self.tags_card.setToolTip(_(TAGS_HINT))
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
        self.previous_label.setText(
            _("Sin datos") if trends.change is None else trends.previous_total.format()
        )
        self.average_label.setText(trends.average.format())
        self.figures.relayout()  # the figures may need more room now

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
            line = _("Ahorro {amount}").format(amount=month.total.format())
            return StackedBar(month.month.short_name, segments, title, (line,), month.month)
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
        lines = [_("Total {amount}").format(amount=month.total.format())] + [
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
            self._category_rows.addWidget(EmptyState(_(NO_MOVEMENTS_TEXT), compact=True))
        for total in trends.categories:
            category = total.category
            link = RecordLink.category(category.id)
            row = CategoryLine(category.color, category.name, link=link)
            row.add(muted_label(percent(total.total, trends.total)))
            row.add(amount_label(total.total))
            row.opened.connect(self.record_requested)
            self._category_rows.addWidget(row)

    def _fill_payees(self, trends: Trends) -> None:
        clear_layout(self._payee_rows)
        named = [p for p in trends.payees if p.payee is not None][:PAYEES_SHOWN]
        without = [p for p in trends.payees if p.payee is None]
        if not trends.payees:
            self._payee_rows.addWidget(EmptyState(_(NO_MOVEMENTS_TEXT), compact=True))
        for total in named + without:
            name = total.payee.name if total.payee else _(NO_PAYEE_LABEL)
            color = self._theme.accent if total.payee else self._theme.border
            link = RecordLink.payee(total.payee.id) if total.payee else None
            row = CategoryLine(color, name, movements_text(total.count), link)
            row.add(muted_label(percent(total.total, trends.total)))
            row.add(amount_label(total.total))
            row.opened.connect(self.record_requested)
            self._payee_rows.addWidget(row)

    def _fill_tags(self, trends: Trends) -> None:
        clear_layout(self._tag_rows)
        for total in trends.tags:
            tag = total.tag
            row = CategoryLine(
                tag.color, tag.name, movements_text(total.count), RecordLink.tag(tag.id)
            )
            row.add(muted_label(percent(total.total, trends.total)))
            row.add(amount_label(total.total))
            row.opened.connect(self.record_requested)
            self._tag_rows.addWidget(row)

    def _set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.chart.set_theme(theme)
        if self._trends is not None:
            self._reload()
