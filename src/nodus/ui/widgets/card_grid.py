"""The one grid of cards in Nodus, for the few items that are looked at one by one.

The columns come from the width alone, never from the page or from how many cards
there are, so every card of every grid is as wide at the same window width: a lone card
takes one column, not the whole row (plan 029a, 5.1). Lists of many items stay lists.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QGridLayout, QLayout, QWidget

from nodus.ui.theme.design import Layout, Space
from nodus.ui.widgets.card import Card


def grid_columns(width: int) -> int:
    """How many cards go in each row of a grid ``width`` pixels wide: as many as fit at
    their minimum width, at most ``Layout.GRID_MAX_COLUMNS``."""
    fits = (width + CardGrid.SPACING) // (Layout.GRID_CARD_MIN_WIDTH + CardGrid.SPACING)
    return min(Layout.GRID_MAX_COLUMNS, max(1, fits))


class CardGrid(QWidget):
    """Cards in rows of equal width, reflowed when the width changes; a row with fewer
    cards leaves its last columns empty. The cards of a row take the height of the
    tallest, with their content at the top, so the figures and bars of a row line up."""

    SPACING = Space.L  # the same gap as between the cards of a page

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(self.SPACING)
        # Asks only for one card's room (see ``minimumSizeHint``), or it could never get
        # narrow enough to reflow.
        self._layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.cards: list[Card] = []
        self._columns = 0
        # The empty cells of the last row hold a bare widget, so their columns keep
        # their width and gap: a grid layout gives an empty column no room, stretch or
        # not, and counts a spacer as empty.
        self._fillers: list[QWidget] = []

    def set_cards(self, cards: list[Card]) -> None:
        """Shows ``cards`` in place of the ones before, which are deleted."""
        for card in self.cards:
            self._layout.removeWidget(card)
            card.deleteLater()
        self.cards = list(cards)
        for card in self.cards:
            card.setParent(self)
            card.body.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._columns = 0  # placed below
        self.relayout()

    def columns(self) -> int:
        """How many cards each row holds now."""
        return self._columns

    def relayout(self) -> None:
        columns = grid_columns(self.width())
        if columns == self._columns:
            return
        self._columns = columns
        for card in self.cards:
            self._layout.removeWidget(card)
        for filler in self._fillers:
            self._layout.removeWidget(filler)
            filler.deleteLater()
        self._fillers = []
        for column in range(self._layout.columnCount()):
            self._layout.setColumnStretch(column, 0)
        for index, card in enumerate(self.cards):
            self._layout.addWidget(card, index // columns, index % columns)
        for index in range(len(self.cards), -(-len(self.cards) // columns) * columns):
            filler = QWidget(self)
            self._layout.addWidget(filler, index // columns, index % columns)
            self._fillers.append(filler)
        for column in range(columns):
            self._layout.setColumnStretch(column, 1)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        widest = max((card.minimumSizeHint().width() for card in self.cards), default=0)
        return QSize(widest, super().minimumSizeHint().height())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.relayout()
