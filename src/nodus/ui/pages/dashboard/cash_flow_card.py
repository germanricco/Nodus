"""Inicio: what was saved in the period, and month by month."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel

from nodus.i18n import N_, _
from nodus.models.period import Month
from nodus.services.reports.dashboard_service import Comparison, MonthFlow
from nodus.ui.text.formatting import rate_text
from nodus.ui.text.labels import unconverted_note
from nodus.ui.theme.design import Space
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card, card_header
from nodus.ui.widgets.change_badge import ChangeBadge
from nodus.ui.widgets.charts.bar_chart import BarChart, flow_bar_groups
from nodus.ui.widgets.charts.chart_base import compact_pesos
from nodus.ui.widgets.charts.share_charts import ProportionBar, Segment
from nodus.ui.widgets.figure_row import FigureRow
from nodus.ui.widgets.figure_tile import FigureTile
from nodus.ui.widgets.money_label import AnimatedMoneyLabel
from nodus.ui.widgets.style import muted_label


class CashFlowCard(Card):
    """What was saved in the period, against the previous one, and month by month; a
    click on a month asks for its movements."""

    month_requested = Signal(object)  # Month

    def __init__(self, theme_manager: ThemeManager) -> None:
        super().__init__()
        theme = theme_manager.theme
        header = card_header(self, _("Flujo de caja"))
        self.change_badge = ChangeBadge()
        self.change_badge.setToolTip(_("Ahorro frente al período anterior"))
        header.addWidget(self.change_badge)
        self.savings_label = AnimatedMoneyLabel(highlight_positive=True)
        self.savings_label.setObjectName("StatValueLarge")
        self.savings_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.caption_label = muted_label("")
        self.body.addWidget(self.savings_label)
        self.body.addWidget(self.caption_label)
        self.body.addSpacing(Space.S)
        self.proportion = ProportionBar(theme)
        self.body.addWidget(self.proportion)
        self.body.addSpacing(Space.S)

        self.income_label = AnimatedMoneyLabel(highlight_positive=True, compact_when_narrow=True)
        self.expenses_label = AnimatedMoneyLabel(compact_when_narrow=True)
        self.saved_label = QLabel()
        tiles = self.figures = FigureRow()
        for caption, value in (
            (N_("Ingresos"), self.income_label),
            (N_("Gastos"), self.expenses_label),
            (N_("Ahorrado"), self.saved_label),
        ):
            tiles.add_tile(FigureTile(_(caption), value))
        self.body.addWidget(tiles)

        self.unconverted_label = muted_label("")
        self.unconverted_label.setWordWrap(True)
        self.body.addWidget(self.unconverted_label)
        trend_title = QLabel(_("MES A MES"))
        trend_title.setObjectName("StatCaption")
        self.body.addSpacing(Space.S)
        self.body.addWidget(trend_title)
        self.chart = BarChart(theme, compact_pesos)
        self._months: list[Month] = []
        self.chart.clicked.connect(lambda index: self.month_requested.emit(self._months[index]))
        self.body.addWidget(self.chart, stretch=1)
        self._theme = theme
        theme_manager.theme_changed.connect(self._set_theme)

    def show_data(self, comparison: Comparison, flow: list[MonthFlow]) -> None:
        summary = comparison.current
        self.savings_label.set_money(summary.savings)
        self.caption_label.setText(" · ".join([_("Ahorro"), summary.period.label()]))
        self.change_badge.set_change(comparison.savings_change)
        self.proportion.set_segments(
            [
                Segment(self._theme.income, summary.income.cents, "income"),
                Segment(self._theme.expense, summary.expenses.cents, "expenses"),
            ]
        )
        self.income_label.set_money(summary.income)
        self.expenses_label.set_money(-summary.expenses)
        self.saved_label.setText(rate_text(summary.savings_rate))
        self.figures.relayout()  # the figures may need more room now
        self.unconverted_label.setText(unconverted_note(summary.unconverted))
        self.unconverted_label.setVisible(bool(summary.unconverted))
        self._months = [month.month for month in flow]
        single_month = len(summary.period.months()) == 1
        self.chart.set_groups(
            flow_bar_groups(flow, summary.period.first_month if single_month else None)
        )

    def _set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.proportion.set_theme(theme)
        self.chart.set_theme(theme)
