"""Inicio: the largest expenses against the previous period."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QVBoxLayout

from nodus.i18n import _
from nodus.services.reports.dashboard_service import Comparison
from nodus.ui.navigation import RecordLink
from nodus.ui.theme.design import Layout, Space
from nodus.ui.widgets.card import Card, card_header
from nodus.ui.widgets.change_badge import ChangeBadge
from nodus.ui.widgets.empty_state import EmptyState
from nodus.ui.widgets.style import clear_layout
from nodus.ui.widgets.tables.category_line import CategoryLine

COMPARISON_COUNT = 6


class ComparisonCard(Card):
    """The categories with the most spending, each against the previous period."""

    record_requested = Signal(object)  # RecordLink

    def __init__(self) -> None:
        super().__init__()
        card_header(self, _("Frente al período anterior"))
        self._rows = QVBoxLayout()
        self._rows.setSpacing(Space.XXS)
        self.body.addLayout(self._rows)
        self.body.addStretch()
        self.rows: list[CategoryLine] = []

    def show_data(self, comparison: Comparison) -> None:
        clear_layout(self._rows)
        self.rows = []
        changes = comparison.categories[:COMPARISON_COUNT]
        if not changes:
            self._rows.addWidget(EmptyState(_("Sin gastos en el período."), compact=True))
        for change in changes:
            category = change.category
            row = CategoryLine(
                category.color,
                category.name,
                change.current.format(),
                RecordLink.category(category.id),
            )
            badge = ChangeBadge(higher_is_better=False, none_text=_("Nueva"))
            # In the row before set_change shows it, or it would flash as its own window.
            row.add(badge)
            badge.set_change(change.change)
            badge.setToolTip(
                _("Período anterior: {amount}").format(amount=change.previous.format())
            )
            badge.setMinimumWidth(Layout.CHANGE_BADGE_MIN_WIDTH)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.opened.connect(self.record_requested)
            self._rows.addWidget(row)
            self.rows.append(row)
