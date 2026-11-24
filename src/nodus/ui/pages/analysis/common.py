"""What the reports of Análisis share: their base class, their cards and table columns."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from nodus.i18n import N_, _
from nodus.models.period import Period
from nodus.ui.widgets.card import Card, card_header
from nodus.ui.widgets.empty_state import NO_MOVEMENTS_TEXT, EmptyState
from nodus.ui.widgets.style import muted_label

# What the change badges of Analysis compare against.
VERSUS_PREVIOUS_TEXT = N_("Frente al período anterior, del mismo largo")
ModelIndex = QModelIndex | QPersistentModelIndex
# The first column of every table.
MONTH = 0


def chart_card(title: str, chart: QWidget) -> tuple[Card, EmptyState, QLabel]:
    """A card with ``chart``, the label shown instead of it when the period is empty and
    the note about movements left out for lack of an exchange rate."""
    card = Card()
    card_header(card, title)
    empty_label = EmptyState(_(NO_MOVEMENTS_TEXT), compact=True)
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
    record_requested = Signal(object)  # RecordLink
    # What the report shows, in a line under its tab: marked with N_(), shown with _().
    DESCRIPTION = ""

    def show_period(self, period: Period) -> None:
        raise NotImplementedError
