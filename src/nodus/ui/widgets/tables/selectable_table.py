"""A table of records where several rows can be chosen and each row has its menu.

Each row starts with a check box and ends with a «⋯». Both are drawn inside the first and
last visible columns rather than as columns of their own, so models, column numbers,
sorting and exports stay as they are. The check boxes show the table's own selection,
not a separate state: a click on a box adds or removes its row, Ctrl+click and
Shift+click work as usual, and the box in the header chooses every row or none.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import (
    QAbstractItemModel,
    QEvent,
    QModelIndex,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QCursor,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QWidget,
)

from nodus.ui.shortcuts import CLEAR_SELECTION
from nodus.ui.theme.design import IconSize, Layout, Line, Radius, Space
from nodus.ui.theme.icons import tinted_pixmap
from nodus.ui.theme.theme_manager import active_theme
from nodus.ui.widgets.tables.row_actions import RowAction, run_default, show_menu
from nodus.ui.widgets.tables.table import (
    configure_record_table,
    draw_cell_background,
    light_row,
)

# Room for the check box at the start of a row and for the «⋯» at its end, in pixels.
CHECK_GUTTER = Layout.CHECK_COLUMN
MORE_GUTTER = Layout.MORE_COLUMN
_BOX = IconSize.M  # as the check boxes of the stylesheet
# A table sorted by its titles, which the stylesheet gives room for the sort arrow: its
# titles' right padding is this much larger than other titles'.
SORTABLE = "SortableTable"
SORT_ARROW_ROOM = Space.XL - Space.S

RowActionsFor = Callable[[int], Sequence[RowAction]]


def paint_check_box(painter: QPainter, area: QRect, state: Qt.CheckState) -> None:
    """A rounded box centered in ``area``: empty, ticked, or with a dash when only some
    rows are chosen."""
    theme = active_theme()
    box = QRectF(area.center().x() - _BOX / 2 + 1, area.center().y() - _BOX / 2 + 1, _BOX, _BOX)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if state == Qt.CheckState.Unchecked:
        painter.setPen(QPen(QColor(theme.text_muted), Line.STROKE))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(box.adjusted(0.5, 0.5, -0.5, -0.5), Radius.S, Radius.S)
    else:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.accent))
        painter.drawRoundedRect(box, Radius.S, Radius.S)
        pen = QPen(QColor(theme.on_accent), Line.THICK)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if state == Qt.CheckState.Checked:
            tick = QPainterPath(QPointF(box.left() + 4, box.center().y() + 0.5))
            tick.lineTo(box.left() + 7, box.bottom() - 4.5)
            tick.lineTo(box.right() - 4, box.top() + 5)
            painter.drawPath(tick)
        else:
            y = box.center().y()
            painter.drawLine(QPointF(box.left() + 4, y), QPointF(box.right() - 4, y))
    painter.restore()


class RowControlsDelegate(QStyledItemDelegate):
    """Paints cells as usual, making room for the check box in the first visible column
    and for the «⋯» in the last one. A table that draws its cells its own way overrides
    ``paint_cell``."""

    def __init__(self, table: SelectableTable) -> None:
        super().__init__(table)
        self._table = table

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        # The row under the mouse lights up whole, as the sidebar's items; a chosen row
        # keeps the selection color.
        if index.row() == self._table.hovered_row and not (
            option.state & QStyle.StateFlag.State_Selected
        ):
            light_row(painter, option)
        item = QStyleOptionViewItem(option)
        self.initStyleOption(item, index)
        content = self._table.content_rect(option.rect, index.column())
        self.paint_cell(painter, item, content, index)
        first, last = self._table.edge_columns()
        if index.column() == first:
            checked = self._table.selectionModel().isRowSelected(index.row(), QModelIndex())
            state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            paint_check_box(painter, self._table.check_rect(option.rect), state)
        if index.column() == last:
            hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
            theme = active_theme()
            pixmap = tinted_pixmap("more", theme.text if hovered else theme.text_muted)
            area = self._table.more_rect(option.rect)
            size = pixmap.deviceIndependentSize()
            painter.drawPixmap(
                QPointF(
                    area.center().x() - size.width() / 2 + 1,
                    area.center().y() - size.height() / 2 + 1,
                ),
                pixmap,
            )

    def paint_cell(
        self,
        painter: QPainter,
        item: QStyleOptionViewItem,
        content: QRect,
        index: QModelIndex,
    ) -> None:
        """The cell's background over all of ``item.rect`` and its text and icon within
        ``content``, the room the controls leave."""
        style = self._table.style()
        if content != item.rect:
            draw_cell_background(painter, item, self._table)
            item.rect = content
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, item, painter, self._table)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        size = super().sizeHint(option, index)
        first, last = self._table.edge_columns()
        if index.column() == first:
            size.setWidth(size.width() + CHECK_GUTTER)
        if index.column() == last:
            size.setWidth(size.width() + MORE_GUTTER)
        return size


class _SelectionHeader(QHeaderView):
    """The header, with the box that chooses every row over the first column and an empty
    space over the «⋯»."""

    def __init__(self, table: SelectableTable) -> None:
        super().__init__(Qt.Orientation.Horizontal, table)
        self._table = table

    def paintSection(self, painter: QPainter, rect: QRect, logical_index: int) -> None:  # noqa: N802
        first = self._table.edge_columns()[0]
        # The title starts and ends where the cells' text does, so it stands over it.
        content = self._table.content_rect(rect, logical_index)
        content.setLeft(content.left() + self._table.title_indent(logical_index))
        last = self._table.edge_columns()[1]
        if logical_index == last and self._table.objectName() == SORTABLE:
            # The room the stylesheet keeps for the sort arrow comes out of the «⋯»'s,
            # empty in the header, so a title at the right still ends where its cells do.
            content.setRight(content.right() + SORT_ARROW_ROOM)
        if content == rect:
            super().paintSection(painter, rect, logical_index)
            return
        theme = active_theme()
        painter.save()
        painter.fillRect(rect, QColor(theme.surface))
        painter.setPen(QColor(theme.border))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        painter.restore()
        painter.save()
        super().paintSection(painter, content, logical_index)
        painter.restore()
        if logical_index == first:
            paint_check_box(painter, self._table.check_rect(rect), self._table.check_state())

    def sectionSizeFromContents(self, logical_index: int) -> QSize:  # noqa: N802
        size = super().sectionSizeFromContents(logical_index)
        first, last = self._table.edge_columns()
        if logical_index == first:
            size.setWidth(size.width() + CHECK_GUTTER)
        if logical_index == last:
            size.setWidth(size.width() + MORE_GUTTER)
        return size

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        x = int(event.position().x())
        section = self.logicalIndexAt(x)
        first, last = self._table.edge_columns()
        if section == first and x < self.sectionViewportPosition(section) + CHECK_GUTTER:
            self._table.toggle_all()
            return
        end = self.sectionViewportPosition(last) + self.sectionSize(last)
        if section == last and x >= end - MORE_GUTTER:
            return  # the empty space over the «⋯» sorts nothing
        super().mousePressEvent(event)


class SelectableTable(QTableView):
    """A record table whose rows can be chosen several at a time, each with its menu.

    ``actions_for(row)`` gives the menu of a row of ``model``, for its «⋯» and for a right
    click. A double click elsewhere than on the controls runs the row's main action (the
    bold one in its menu). The row under the mouse lights up (``hovered_row``) without
    being chosen.
    """

    selection_changed = Signal()

    def __init__(
        self,
        model: QAbstractItemModel,
        stretch_column: int,
        actions_for: RowActionsFor,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._actions_for = actions_for
        self.hovered_row = -1
        self._title_indents: dict[int, int] = {}
        self.setHorizontalHeader(_SelectionHeader(self))
        configure_record_table(self, model, stretch_column)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setItemDelegate(RowControlsDelegate(self))

        self.setMouseTracking(True)
        self.selectionModel().selectionChanged.connect(self._on_selection_changed)
        model.modelReset.connect(self._on_selection_changed)

    def setSortingEnabled(self, enable: bool) -> None:  # noqa: N802
        """Sorting by a click on a column's title, with the hand over the titles and room
        for the sort arrow (``#SortableTable``). The header this table puts in place of
        Qt's takes no clicks until told to, and its sort arrow would then promise what a
        click does not do."""
        super().setSortingEnabled(enable)
        self.setObjectName(SORTABLE if enable else "")
        self.style().unpolish(self)
        self.style().polish(self)
        header = self.horizontalHeader()
        header.setSectionsClickable(enable)
        cursor = Qt.CursorShape.PointingHandCursor if enable else Qt.CursorShape.ArrowCursor
        header.setCursor(cursor)

    # Selection

    def selected_rows(self) -> list[int]:
        """The chosen rows of the model, top to bottom."""
        return sorted(index.row() for index in self.selectionModel().selectedRows())

    def check_state(self) -> Qt.CheckState:
        chosen, total = len(self.selectionModel().selectedRows()), self.model().rowCount()
        if chosen == 0:
            return Qt.CheckState.Unchecked
        return Qt.CheckState.Checked if chosen == total else Qt.CheckState.PartiallyChecked

    def toggle_all(self) -> None:
        """Chooses every row, or none if they all were."""
        if self.check_state() == Qt.CheckState.Checked:
            self.clearSelection()
        else:
            self.selectAll()

    def toggle_row(self, row: int) -> None:
        index = self.model().index(row, 0)
        flags = (
            self.selectionModel().SelectionFlag.Toggle | self.selectionModel().SelectionFlag.Rows
        )
        self.selectionModel().select(index, flags)
        self.selectionModel().setCurrentIndex(index, self.selectionModel().SelectionFlag.NoUpdate)

    def open_menu(self, row: int, position: QPoint) -> None:
        """The menu of ``row`` at ``position`` (global). A row outside the selection
        becomes the only one chosen, so it is clear which row the menu acts on."""
        if not self.selectionModel().isRowSelected(row, QModelIndex()):
            self.selectRow(row)
        menu = show_menu(self, self._actions_for(row), position)
        menu.aboutToHide.connect(self._hover_where_the_mouse_is)

    def actions_for(self, row: int) -> Sequence[RowAction]:
        return self._actions_for(row)

    def indent_title(self, column: int, pixels: int) -> None:
        """Moves ``column``'s title ``pixels`` to the right, to stand over its cells' text
        when they start with a mark, such as a category's dot."""
        self._title_indents[column] = pixels
        self.horizontalHeader().viewport().update()

    def title_indent(self, column: int) -> int:
        return self._title_indents.get(column, 0)

    # Geometry of the controls

    def edge_columns(self) -> tuple[int, int]:
        """The first and last visible columns, which hold the check box and the «⋯»."""
        header = self.horizontalHeader()
        visible = [
            header.logicalIndex(visual)
            for visual in range(header.count())
            if not header.isSectionHidden(header.logicalIndex(visual))
        ]
        return (visible[0], visible[-1]) if visible else (-1, -1)

    @staticmethod
    def check_rect(cell: QRect) -> QRect:
        return QRect(cell.left(), cell.top(), CHECK_GUTTER, cell.height())

    @staticmethod
    def more_rect(cell: QRect) -> QRect:
        return QRect(cell.right() - MORE_GUTTER + 1, cell.top(), MORE_GUTTER, cell.height())

    def content_rect(self, cell: QRect, column: int) -> QRect:
        first, last = self.edge_columns()
        content = QRect(cell)
        if column == first:
            content.setLeft(cell.left() + CHECK_GUTTER - 8)  # the item padding adds 8 back
        if column == last:
            content.setRight(cell.right() - MORE_GUTTER + 6)
        return content

    def _control_at(self, position: QPoint) -> tuple[str | None, QModelIndex]:
        """Which control is under ``position`` (viewport): "check", "more" or None."""
        index = self.indexAt(position)
        if not index.isValid():
            return None, index
        cell = self.visualRect(index)
        first, last = self.edge_columns()
        if index.column() == first and self.check_rect(cell).contains(position):
            return "check", index
        if index.column() == last and self.more_rect(cell).contains(position):
            return "more", index
        return None, index

    # Mouse and keyboard

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            control, index = self._control_at(event.position().toPoint())
            if control == "check":
                self.toggle_row(index.row())
                return
            if control == "more":
                cell = self.more_rect(self.visualRect(index))
                self.open_menu(index.row(), self.viewport().mapToGlobal(cell.bottomLeft()))
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        control, index = self._control_at(event.position().toPoint())
        if control is not None or not index.isValid():
            return
        super().mouseDoubleClickEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            run_default(self._actions_for(index.row()))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        super().mouseMoveEvent(event)
        control, index = self._control_at(event.position().toPoint())
        cursor = Qt.CursorShape.PointingHandCursor if control else Qt.CursorShape.ArrowCursor
        self.viewport().setCursor(cursor)
        self._set_hovered_row(index.row() if index.isValid() else -1)

    def viewportEvent(self, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Leave:
            self._set_hovered_row(-1)
        return super().viewportEvent(event)

    def _hover_where_the_mouse_is(self) -> None:
        """After a menu closes, the light goes back to the row under the mouse, if any:
        the menu held the mouse, so the table never saw it move or leave."""
        position = self.viewport().mapFromGlobal(QCursor.pos())
        inside = self.viewport().rect().contains(position)
        self._set_hovered_row(self.indexAt(position).row() if inside else -1)

    def _set_hovered_row(self, row: int) -> None:
        if row != self.hovered_row:
            self.hovered_row = row
            self.viewport().update()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: N802
        index = self.indexAt(event.pos())
        if index.isValid():
            self.open_menu(index.row(), event.globalPos())

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if CLEAR_SELECTION.matches(event) and self.selectionModel().hasSelection():
            self.clearSelection()
            return
        super().keyPressEvent(event)

    def _on_selection_changed(self) -> None:
        # Every box shows the selection, and the header's sums it up.
        self.viewport().update()
        self.horizontalHeader().viewport().update()
        self.selection_changed.emit()
