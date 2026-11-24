"""Inicio: where the money went, category by category, against the previous period."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel

from nodus.i18n import N_, _
from nodus.models.money import Money
from nodus.services.conversion import relative_change
from nodus.services.reports.dashboard_service import CategoryChange, Comparison
from nodus.ui.navigation import RecordLink
from nodus.ui.text.formatting import percent
from nodus.ui.theme.design import Layout
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card, titled_figure
from nodus.ui.widgets.change_badge import ChangeBadge
from nodus.ui.widgets.charts.chart_base import shown_fractions
from nodus.ui.widgets.charts.share_bar import ShareBar
from nodus.ui.widgets.empty_state import EmptyState
from nodus.ui.widgets.style import amount_label, clear_layout
from nodus.ui.widgets.tables.category_line import CategoryLine
from nodus.ui.widgets.tables.row_layout import row_list

# Categories listed one by one; the rest are added up as one line.
LISTED_CATEGORIES = 6
REST_LABEL = N_("Resto")


@dataclass(frozen=True)
class CategoryItem:
    """One line of the card: a category, or the rest added up (``link`` None)."""

    key: int | None  # the category's id; None for the rest
    name: str
    color: str
    current: Money
    previous: Money
    link: RecordLink | None

    @property
    def change(self) -> float | None:
        return relative_change(self.current, self.previous)


class CategoriesCard(Card):
    """Where the money went in the period, from the whole to its parts: the total spent
    under the title, with its change against the previous period, then the categories
    that took the most, each with a bar of its share on the same base, its amount and its
    own change; the rest in one line. A click on a category opens its page (plan 029a,
    5.7)."""

    record_requested = Signal(object)  # RecordLink

    def __init__(self, theme_manager: ThemeManager) -> None:
        super().__init__()
        self._theme_manager = theme_manager
        self.total_label = QLabel()
        header = titled_figure(self, _("Gastos por categoría"), self.total_label)
        self.change_badge = ChangeBadge(higher_is_better=False)
        self.change_badge.setToolTip(_("Gastos frente al período anterior"))
        header.addWidget(self.change_badge, alignment=Qt.AlignmentFlag.AlignTop)
        self._rows = row_list()
        self.body.addLayout(self._rows)
        self.body.addStretch()
        self.rows: list[CategoryLine] = []
        self.bars: dict[int | None, ShareBar] = {}

    def show_data(self, comparison: Comparison) -> None:
        summary = comparison.current
        self.total_label.setText(summary.expenses.format())
        self.change_badge.set_change(comparison.expenses_change)
        starts = shown_fractions(self.bars)
        clear_layout(self._rows)
        self.rows, self.bars = [], {}
        items = self._items(comparison.categories)
        if not items:
            self._rows.addWidget(EmptyState(_("Sin gastos en el período."), compact=True))
        theme = self._theme_manager.theme
        total = summary.expenses
        for item in items:
            row = CategoryLine(item.color, item.name, link=item.link)
            share = item.current.cents / total.cents if total.cents > 0 else 0.0
            # Half of the room left, so every bar starts and ends in the same place.
            bar = ShareBar(theme, max(0.0, share), item.color, starts.get(item.key))
            bar.setMinimumWidth(Layout.SHARE_BAR_MIN_WIDTH)
            row.add(bar, stretch=1)
            bar.setToolTip(percent(item.current, total))
            amount = row.add(amount_label(item.current))
            amount.setMinimumWidth(Layout.SHARE_AMOUNT_WIDTH)
            badge = ChangeBadge(higher_is_better=False, none_text=_("Nueva"))
            # In the row before set_change shows it, or it would flash as its own window.
            row.add(badge)
            badge.set_change(item.change)
            badge.setToolTip(_("Período anterior: {amount}").format(amount=item.previous.format()))
            badge.setMinimumWidth(Layout.CHANGE_BADGE_MIN_WIDTH)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.opened.connect(self.record_requested)
            self._rows.addWidget(row)
            self.rows.append(row)
            self.bars[item.key] = bar

    def _items(self, changes: list[CategoryChange]) -> list[CategoryItem]:
        """The categories that took the most, and the rest added up as one line that
        opens nothing, in the muted color."""
        items = [
            CategoryItem(
                c.category.id,
                c.category.name,
                c.category.color,
                c.current,
                c.previous,
                RecordLink.category(c.category.id),
            )
            for c in changes[:LISTED_CATEGORIES]
        ]
        rest = changes[LISTED_CATEGORIES:]
        if rest:
            current = sum((c.current for c in rest[1:]), rest[0].current)
            previous = sum((c.previous for c in rest[1:]), rest[0].previous)
            color = self._theme_manager.theme.text_muted
            items.append(CategoryItem(None, _(REST_LABEL), color, current, previous, None))
        return items
