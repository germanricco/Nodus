"""Inicio: where the money went, in a ring with its legend."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QBoxLayout, QVBoxLayout, QWidget

from nodus.i18n import N_, _
from nodus.models.money import Money
from nodus.services.reports.dashboard_service import CategoryTotal, PeriodSummary
from nodus.ui.text.formatting import percent
from nodus.ui.theme.design import Layout, Space
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card, card_header
from nodus.ui.widgets.change_badge import ChangeBadge
from nodus.ui.widgets.charts.share_charts import DonutChart, Segment
from nodus.ui.widgets.style import amount_label, clear_layout, muted_label
from nodus.ui.widgets.tables.category_line import CategoryLine

# Categories listed beside the donut; the rest are added up as one line.
LEGEND_COUNT = 6
REST_LABEL = N_("Resto")


class ExpensesCard(Card):
    """Where the money went: an interactive ring with its legend.

    Hovering a slice or a legend row highlights both; clicking either emits
    ``category_clicked`` with the category's id.
    """

    category_clicked = Signal(int)

    def __init__(self, theme_manager: ThemeManager) -> None:
        super().__init__()
        self._theme_manager = theme_manager
        header = card_header(self, _("Gastos por categoría"))
        self.change_badge = ChangeBadge(higher_is_better=False)
        self.change_badge.setToolTip(_("Gastos frente al período anterior"))
        header.addWidget(self.change_badge)
        self.donut = DonutChart(theme_manager.theme)
        self.donut.segment_hovered.connect(self._highlight_row)
        self.donut.segment_clicked.connect(self._click_item)
        self.legend_panel = QWidget()
        self._legend = QVBoxLayout(self.legend_panel)
        self._legend.setContentsMargins(0, 0, 0, 0)
        self._legend.setSpacing(0)
        self._chart_area = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        self._chart_area.setSpacing(Space.L)
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
            _("Total") if items else _("Sin gastos"),
            summary.expenses if items else None,
            _("en el período"),
        )
        clear_layout(self._legend)
        self.rows = []
        for index, (category_id, name, color, total) in enumerate(items):
            row = CategoryLine(color, name, clickable=category_id is not None)
            row.add(muted_label(percent(total, summary.expenses)))
            amount = amount_label(total)
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
        return (
            room >= self.donut.minimumWidth() + self._chart_area.spacing() + Layout.LEGEND_MIN_WIDTH
        )

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
        self.legend_panel.setMinimumWidth(Layout.LEGEND_MIN_WIDTH if beside else 0)
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
            items.append((None, _(REST_LABEL), self._theme_manager.theme.text_muted, rest_total))
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
