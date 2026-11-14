"""A row of figure tiles that wraps onto more rows when the page is too narrow for it."""

from __future__ import annotations

import math

from PySide6.QtCore import QSize
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QBoxLayout, QHBoxLayout, QLayout, QVBoxLayout, QWidget

from nodus.ui.theme.design import Space


def balanced_columns(count: int, fits: int) -> int:
    """How many tiles go in each row: as many as fit, spread evenly, so five tiles that
    fit three to a row go three and two rather than three, one and one."""
    if count <= 0:
        return 1
    fits = max(1, min(fits, count))
    rows = math.ceil(count / fits)
    return math.ceil(count / rows)


class FigureRow(QWidget):
    """The key figures of a page side by side, sharing the width. When the widest tile
    would no longer fit its figure, the tiles go onto two or more rows instead of being
    cut; tiles that are hidden take no place.

    Whoever shows or hides a tile, or changes its text, calls ``relayout``.
    """

    SPACING = Space.M

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(self.SPACING)
        # The row asks only for the room of one tile (see ``minimumSizeHint``), not for
        # that of every tile side by side, or it could never get narrow enough to wrap.
        self._layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.tiles: list[QWidget] = []
        self._columns = 0

    def add_tile(self, tile: QWidget) -> None:
        tile.setParent(self)
        self.tiles.append(tile)
        self._columns = 0  # placed on the next relayout
        self.relayout()

    def columns(self) -> int:
        """How many tiles each row holds now."""
        return self._columns

    def relayout(self) -> None:
        shown = self._shown()
        columns = balanced_columns(len(shown), self._fitting(shown))
        if columns == self._columns and self._placed() == shown:
            return
        self._columns = columns
        while (item := self._layout.takeAt(0)) is not None:
            row = item.layout()
            while row is not None and row.takeAt(0) is not None:
                pass
            if row is not None:
                row.setParent(None)
        for start in range(0, len(shown), columns):
            row = QHBoxLayout()
            row.setSpacing(self.SPACING)
            for tile in shown[start : start + columns]:
                row.addWidget(tile, stretch=1)
            self._layout.addLayout(row)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        widest = max((tile.minimumSizeHint().width() for tile in self._shown()), default=0)
        return QSize(widest, super().minimumSizeHint().height())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.relayout()

    def _shown(self) -> list[QWidget]:
        return [tile for tile in self.tiles if not tile.isHidden()]

    def _fitting(self, shown: list[QWidget]) -> int:
        """How many of the widest tile fit in the width there is."""
        if not shown:
            return 1
        widest = max(tile.sizeHint().width() for tile in shown)
        return max(1, (self.width() + self.SPACING) // (widest + self.SPACING))

    def _placed(self) -> list[QWidget]:
        placed = []
        for index in range(self._layout.count()):
            row = self._layout.itemAt(index).layout()
            if isinstance(row, QBoxLayout):
                placed += [row.itemAt(i).widget() for i in range(row.count())]
        return placed
