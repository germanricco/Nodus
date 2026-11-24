"""A vertical list whose rows the user reorders by dragging a handle, and drags to
another list of the same family (an account to another group)."""

from __future__ import annotations

import weakref
from collections.abc import Hashable

from PySide6.QtCore import QByteArray, QEvent, QMimeData, QObject, QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QDrag,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPalette,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from nodus.i18n import _
from nodus.ui.shortcuts import MOVE_ROW_DOWN, MOVE_ROW_UP
from nodus.ui.theme.design import Line, Opacity, Radius, Space
from nodus.ui.widgets.style import set_style_property

# What a dragged row carries: "<list id>:<row index>". A list accepts its own rows, and
# those of the lists of its family.
ROW_MIME_TYPE = "application/x-nodus-row"

# Every list alive, by id, to find where a dragged row comes from.
_LISTS: weakref.WeakValueDictionary[int, ReorderableList] = weakref.WeakValueDictionary()


class DragHandle(QWidget):
    """Six dots that show a row can be dragged; the drag starts here, not on the row, so
    the row's buttons keep working with ordinary clicks."""

    DOT = 3  # geometry
    GAP = 3  # geometry

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(self.width_for())
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(_("Arrastrar para ordenar"))
        self._press: QPoint | None = None

    @classmethod
    def width_for(cls) -> int:
        return 2 * cls.DOT + cls.GAP + Space.S

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
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


def drag_pixmap(row: QWidget) -> QPixmap:
    """The picture that follows the mouse while a row is dragged: the row as it looks on
    its card, background included, slightly see-through and outlined in the accent, so it
    reads as picked up and the line where it lands shows beneath it."""
    window = row.window()
    shot = window.grab(QRect(row.mapTo(window, QPoint(0, 0)), row.size()))
    ratio = shot.devicePixelRatio()
    pixmap = QPixmap(shot.size())
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.save()
    painter.setOpacity(Opacity.DRAGGED)
    painter.drawPixmap(0, 0, shot)
    painter.restore()
    painter.setPen(QPen(row.palette().color(QPalette.ColorRole.Highlight), Line.THIN))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    edge = QRectF(0, 0, row.width(), row.height()).adjusted(0.5, 0.5, -0.5, -0.5)
    painter.drawRoundedRect(edge, Radius.M, Radius.M)
    painter.end()
    return pixmap


class _ListRow(QWidget):
    """A handle beside the caller's widget; knows its list to start a drag from it."""

    SPACING = Space.XS

    def __init__(self, owner: ReorderableList, index: int, content: QWidget) -> None:
        super().__init__()
        self._owner = owner
        self.index = index
        self.content = content
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.SPACING)
        self.handle = DragHandle()
        layout.addWidget(self.handle)
        layout.addWidget(content, stretch=1)

    def start_drag(self) -> None:
        drag = QDrag(self)
        drag.setMimeData(self._owner.mime_data(self.index))
        drag.setPixmap(drag_pixmap(self))
        drag.setHotSpot(QPoint(self.handle.width() // 2, self.height() // 2))
        self.handle.setCursor(Qt.CursorShape.ClosedHandCursor)
        # The row stays where it was, faded, as the gap it leaves.
        faded = QGraphicsOpacityEffect(self)
        faded.setOpacity(Opacity.FADED)
        self.setGraphicsEffect(faded)
        try:
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            self.setGraphicsEffect(None)
            self.handle.setCursor(Qt.CursorShape.OpenHandCursor)
            self._owner.hide_indicator()


class ReorderableList(QWidget):
    """Rows identified by a key, in order; dragging one by its handle to another place
    emits ``order_changed`` with every key in the new order. The list does not reorder
    itself: whoever saves the order rebuilds it, so what is shown is always what is saved.

    Lists that share a ``family`` take each other's rows: a row dropped here from another
    one emits ``row_received`` with its key and the gap where it lands. Without a family,
    a list only takes its own rows.
    """

    order_changed = Signal(list)
    row_received = Signal(object, int)  # key, gap

    SPACING = 0  # the rows touch, as in every list (``row_layout.py``)

    def __init__(self, parent: QWidget | None = None, family: str | None = None) -> None:
        super().__init__(parent)
        self.family = family
        _LISTS[id(self)] = self
        self.setAcceptDrops(True)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(self.SPACING)
        self._keys: list[Hashable] = []
        self._rows: list[_ListRow] = []
        self._placeholder: QLabel | None = None
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
        widget.installEventFilter(self)  # Alt+↑ and Alt+↓ move it
        if self._placeholder is not None:
            self._placeholder.hide()

    def set_placeholder(self, text: str) -> None:
        """What an empty list shows, framed as the place to drop a row."""
        if self._placeholder is None:
            self._placeholder = QLabel()
            self._placeholder.setObjectName("DropZone")
            self._placeholder.setWordWrap(True)
            self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._layout.insertWidget(0, self._placeholder)
        self._placeholder.setText(text)
        self._placeholder.setVisible(not self._rows)

    @property
    def placeholder(self) -> QLabel | None:
        return self._placeholder

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

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Alt+↑ and Alt+↓ on a row move it one place, as dragging it would."""
        if event.type() != QEvent.Type.KeyPress or not isinstance(event, QKeyEvent):
            return False
        index = next((i for i, row in enumerate(self._rows) if row.content is watched), None)
        if index is None:
            return False
        if MOVE_ROW_UP.matches(event):
            if index > 0:
                self.move(index, index - 1)
            return True
        if MOVE_ROW_DOWN.matches(event):
            if index < len(self._rows) - 1:
                self.move(index, index + 2)
            return True
        return False

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

    # Drag and drop

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if self._source(event) is not None:
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        if self._source(event) is None:
            return
        event.acceptProposedAction()
        self._show_indicator(self.insertion_index(event.position().toPoint().y()))

    def dragLeaveEvent(self, _event: QDragLeaveEvent) -> None:  # noqa: N802
        self.hide_indicator()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        self.hide_indicator()
        source = self._source(event)
        if source is None:
            return
        event.acceptProposedAction()
        owner, index = source
        gap = self.insertion_index(event.position().toPoint().y())
        if owner is self:
            self.move(index, gap)
        else:
            self.row_received.emit(owner.keys()[index], gap)

    def hide_indicator(self) -> None:
        self._indicator.hide()
        self._set_drop_zone_active(False)

    def _source(self, event: QDropEvent) -> tuple[ReorderableList, int] | None:
        """The list and index of the row being dragged, if this list takes it: its own,
        or one of its family's."""
        mime = event.mimeData()
        if not mime.hasFormat(ROW_MIME_TYPE):
            return None
        owner_id, _separator, index = bytes(mime.data(ROW_MIME_TYPE)).decode().partition(":")
        owner = _LISTS.get(int(owner_id))
        if owner is None:
            return None
        if owner is self or (self.family is not None and owner.family == self.family):
            return owner, int(index)
        return None

    def _set_drop_zone_active(self, active: bool) -> None:
        """Lights the empty list's frame while a row is over it."""
        zone = self._placeholder
        if zone is not None and zone.property("active") != active:
            set_style_property(zone, "active", active)

    def _show_indicator(self, gap: int) -> None:
        """Draws the line in the middle of the space before row ``gap``, or after the last;
        an empty list lights its frame instead."""
        if not self._rows:
            self._set_drop_zone_active(True)
            return
        if gap < len(self._rows):
            y = self._rows[gap].geometry().top() - self.SPACING // 2
        else:
            y = self._rows[-1].geometry().bottom() + self.SPACING // 2
        self._indicator.setGeometry(0, min(max(0, y - 1), self.height() - 2), self.width(), 2)
        self._indicator.raise_()
        self._indicator.show()
