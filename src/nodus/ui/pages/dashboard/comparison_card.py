"""Inicio: the largest expenses against the previous period."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QVBoxLayout

from nodus.i18n import _
from nodus.services.reports.dashboard_service import Comparison
from nodus.ui.theme.design import Layout, Space
from nodus.ui.widgets.card import Card, card_header
from nodus.ui.widgets.change_badge import ChangeBadge
from nodus.ui.widgets.empty_state import EmptyState
from nodus.ui.widgets.style import clear_layout
from nodus.ui.widgets.tables.category_line import CategoryLine

COMPARISON_COUNT = 6


class ComparisonCard(Card):
    """The categories with the most spending, each against the previous period."""

    category_clicked = Signal(int)

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
            row = CategoryLine(change.category.color, change.category.name, change.current.format())
            badge = ChangeBadge(higher_is_better=False, none_text=_("Nueva"))
            # In the row before set_change shows it, or it would flash as its own window.
            row.add(badge)
            badge.set_change(change.change)
            badge.setToolTip(
                _("Período anterior: {amount}").format(amount=change.previous.format())
            )
            badge.setMinimumWidth(Layout.CHANGE_BADGE_MIN_WIDTH)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.clicked.connect(lambda c=change.category.id: self.category_clicked.emit(c))
            row.hovered.connect(lambda on, r=row: r.set_highlighted(on))
            self._rows.addWidget(row)
            self.rows.append(row)
