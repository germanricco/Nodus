"""A layout that places items in a row and wraps to a new line when they do not fit."""

from __future__ import annotations

from PySide6.QtCore import QMargins, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QWidget


class FlowLayout(QLayout):
    """Left to right, like words in a paragraph.

    A row of labels in a box layout cannot get narrower than all of them together, which
    pushes everything around it off the window; this one gives up width for height.
    With ``last_to_the_right``, the last item sits against the right edge of its line,
    like a row that ends in a stretch. An item added with ``add_growing``, such as a
    search box, takes what its line leaves.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        h_spacing: int = 20,
        v_spacing: int = 6,
        last_to_the_right: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self._last_to_the_right = last_to_the_right
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._items: list[QLayoutItem] = []
        self._growing: list[QWidget] = []

    def add_growing(self, widget: QWidget) -> None:
        """Adds ``widget`` to take what its line leaves."""
        self.addWidget(widget)
        self._growing.append(widget)

    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._arrange(QRect(0, 0, width, 0), move=False)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._arrange(rect, move=True)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        """As narrow as the widest single item: anything wider wraps."""
        size = QSize()
        for item in self._visible_items():
            size = size.expandedTo(item.minimumSize())
        margins: QMargins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _visible_items(self) -> list[QLayoutItem]:
        return [item for item in self._items if not item.isEmpty()]

    def _arrange(self, rect: QRect, move: bool) -> int:
        """Places the items inside ``rect`` (only when ``move``), each centered on its
        line; returns the height used. A line takes as many items as fit at their
        minimum width, then gives them back what it can of their natural width, and the
        growing ones (``add_growing``) share what is still left."""
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        items = self._visible_items()
        lines: list[list[QLayoutItem]] = []
        x = area.x()
        for item in items:
            width = item.minimumSize().width()
            if not lines or (x > area.x() and x + width > area.right() + 1):
                lines.append([])
                x = area.x()
            lines[-1].append(item)
            x += width + self._h_spacing
        y = area.y()
        for index, line in enumerate(lines):
            if index:
                y += self._v_spacing
            height = max(item.sizeHint().height() for item in line)
            if move:
                self._place_line(line, area, y, height, items[-1])
            y += height
        return y - rect.y() + margins.bottom()

    def _widths(self, line: list[QLayoutItem], room: int) -> list[int]:
        """Each item's width in a line ``room`` wide."""
        mins = [item.minimumSize().width() for item in line]
        hints = [max(item.sizeHint().width(), low) for item, low in zip(line, mins, strict=True)]
        left = room - sum(mins) - self._h_spacing * (len(line) - 1)
        wanted = sum(hints) - sum(mins)
        if left < wanted:  # short of room: each gets the same part of what it wants
            return [
                low + (high - low) * max(0, left) // wanted
                for low, high in zip(mins, hints, strict=True)
            ]
        widths = hints
        growing = [i for i, item in enumerate(line) if item.widget() in self._growing]
        for i in growing:
            widths[i] += (left - wanted) // len(growing)
        return widths

    def _place_line(
        self, line: list[QLayoutItem], area: QRect, y: int, height: int, last: QLayoutItem
    ) -> None:
        x = area.x()
        for item, width in zip(line, self._widths(line, area.width()), strict=True):
            if self._last_to_the_right and item is last:
                x = max(x, area.right() + 1 - width)
            hint = item.sizeHint()
            top = y + (height - hint.height()) // 2
            item.setGeometry(QRect(x, top, width, hint.height()))
            x += width + self._h_spacing
