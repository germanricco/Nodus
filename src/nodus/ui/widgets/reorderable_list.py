"""A vertical list whose rows the user reorders by dragging a handle."""

from __future__ import annotations

from collections.abc import Hashable

from PySide6.QtCore import QByteArray, QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import (
    QDrag,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QMouseEvent,
    QPainter,
    QPalette,
)
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QVBoxLayout, QWidget

from nodus.ui.theme.design import Line, Space

# What a dragged row carries: "<list id>:<row index>", so a list only accepts its own rows.
ROW_MIME_TYPE = "application/x-nodus-row"


class DragHandle(QWidget):
    """Six dots that show a row can be dragged; the drag starts here, not on the row, so
    the row's buttons keep working with ordinary clicks."""

    DOT = 3  # geometry
    GAP = 3  # geometry

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(self.width_for())
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Arrastrar para ordenar")
        self._press: QPoint | None = None

    @classmethod
    def width_for(cls) -> int:
        return 2 * cls.DOT + cls.GAP + Space.S

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.palette().color(QPalette.ColorRole.PlaceholderText))
        step = self.DOT + self.GAP
        left = (self.width() - (2 * self.DOT + self.GAP)) // 2
        top = (self.height() - (3 * self.DOT + 2 * self.GAP)) // 2
        for column in range(2):
            for row in range(3):
                painter.drawEllipse(left + column * step, top + row * step, self.DOT, self.DOT)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.position().toPoint()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._press is None:
            return
        moved = (event.position().toPoint() - self._press).manhattanLength()
        if moved >= QApplication.startDragDistance():
            self._press = None
            row = self.parentWidget()
            if isinstance(row, _ListRow):
                row.start_drag()

    def mouseReleaseEvent(self, _event: QMouseEvent) -> None:  # noqa: N802
        self._press = None


def handle_indent() -> int:
    """How far a list's handle pushes its rows to the right, so a row outside a list (the
    only one of its group) lines up with those inside one."""
    return DragHandle.width_for() + _ListRow.SPACING


class _ListRow(QWidget):
    """A handle beside the caller's widget; knows its list to start a drag from it."""

    SPACING = Space.XS

    def __init__(self, owner: ReorderableList, index: int, content: QWidget) -> None:
        super().__init__()
        self._owner = owner
        self.index = index
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.SPACING)
        self.handle = DragHandle()
        layout.addWidget(self.handle)
        layout.addWidget(content, stretch=1)

    def start_drag(self) -> None:
        drag = QDrag(self)
        drag.setMimeData(self._owner.mime_data(self.index))
        drag.setPixmap(self.grab())
        drag.setHotSpot(QPoint(self.handle.width() // 2, self.height() // 2))
        self.handle.setCursor(Qt.CursorShape.ClosedHandCursor)
        drag.exec(Qt.DropAction.MoveAction)
        self.handle.setCursor(Qt.CursorShape.OpenHandCursor)
        self._owner.hide_indicator()


class ReorderableList(QWidget):
    """Rows identified by a key, in order; dragging one by its handle to another place
    emits ``order_changed`` with every key in the new order. The list does not reorder
    itself: whoever saves the order rebuilds it, so what is shown is always what is saved.
    """

    order_changed = Signal(list)

    SPACING = Space.S  # as between the rows of a Card, so a reorderable list looks the same

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(self.SPACING)
        self._keys: list[Hashable] = []
        self._rows: list[_ListRow] = []
        # A line across the gap where the dragged row would land.
        self._indicator = QFrame(self)
        self._indicator.setObjectName("DropIndicator")
        self._indicator.setFixedHeight(Line.THICK)
        self._indicator.hide()

    def add_row(self, key: Hashable, widget: QWidget) -> None:
        row = _ListRow(self, len(self._rows), widget)
        self._keys.append(key)
        self._rows.append(row)
        self._layout.addWidget(row)

    def keys(self) -> list[Hashable]:
        return list(self._keys)

    def rows(self) -> list[QWidget]:
        return list(self._rows)

    def insertion_index(self, y: int) -> int:
        """Where a row dropped at height ``y`` goes: before the first row whose middle is
        below ``y``, or at the end."""
        for index, row in enumerate(self._rows):
            if y < row.geometry().center().y():
                return index
        return len(self._rows)

    def move(self, source: int, target: int) -> None:
        """Moves row ``source`` to the gap ``target`` (0 is before the first row, the row
        count after the last) and emits the new order, unless nothing changes."""
        if target in (source, source + 1):
            return
        keys = self.keys()
        key = keys.pop(source)
        keys.insert(target - 1 if target > source else target, key)
        self.order_changed.emit(keys)

    def mime_data(self, index: int) -> QMimeData:
        """What dragging row ``index`` carries."""
        mime = QMimeData()
        mime.setData(ROW_MIME_TYPE, QByteArray(f"{id(self)}:{index}".encode()))
        return mime

    def hide_indicator(self) -> None:
        self._indicator.hide()

    # Drag and drop

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if self._source_index(event) is not None:
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        if self._source_index(event) is None:
            return
        event.acceptProposedAction()
        self._show_indicator(self.insertion_index(event.position().toPoint().y()))

    def dragLeaveEvent(self, _event) -> None:  # noqa: N802
        self.hide_indicator()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        self.hide_indicator()
        source = self._source_index(event)
        if source is None:
            return
        event.acceptProposedAction()
        self.move(source, self.insertion_index(event.position().toPoint().y()))

    def _source_index(self, event: QDropEvent) -> int | None:
        """The index of the row being dragged, if it comes from this list."""
        mime = event.mimeData()
        if not mime.hasFormat(ROW_MIME_TYPE):
            return None
        owner, _, index = bytes(mime.data(ROW_MIME_TYPE)).decode().partition(":")
        return int(index) if owner == str(id(self)) else None

    def _show_indicator(self, gap: int) -> None:
        """Draws the line in the middle of the space before row ``gap``, or after the last."""
        if gap < len(self._rows):
            y = self._rows[gap].geometry().top() - self.SPACING // 2
        else:
            y = self._rows[-1].geometry().bottom() + self.SPACING // 2
        self._indicator.setGeometry(0, min(max(0, y - 1), self.height() - 2), self.width(), 2)
        self._indicator.raise_()
        self._indicator.show()
