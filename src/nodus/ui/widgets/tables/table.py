"""Read-only tables of records, as the transactions and payees pages show them."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QAbstractItemModel, QEvent, QModelIndex, QObject, Qt
from PySide6.QtGui import QColor, QKeyEvent, QKeySequence, QMouseEvent, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
)

from nodus.ui.theme.theme_manager import active_theme


def record_table(model: QAbstractItemModel, stretch_column: int) -> QTableView:
    """A table of single whole-row selection, without grid or editing, whose columns fit
    their content except ``stretch_column``, which takes the remaining width."""
    table = QTableView()
    configure_record_table(table, model, stretch_column)
    return table


def configure_record_table(
    table: QTableView, model: QAbstractItemModel, stretch_column: int
) -> None:
    """Sets up ``table`` as ``record_table`` describes, for tables of other classes."""
    table.setModel(model)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.verticalHeader().hide()
    table.verticalHeader().setDefaultSectionSize(40)
    header = table.horizontalHeader()
    header.setHighlightSections(False)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    # Set for the whole header, so columns a model adds later also fit their content.
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(stretch_column, QHeaderView.ResizeMode.Stretch)


DELETE_KEY_HINT = "También con la tecla Supr"


class _DeleteKeyFilter(QObject):
    """Turns a Supr press on the table it watches into a call to ``delete``."""

    def __init__(self, table: QTableView, delete: Callable[[], None]) -> None:
        super().__init__(table)
        self._delete = delete

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if (
            event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and event.matches(QKeySequence.StandardKey.Delete)
        ):
            self._delete()
            return True
        return False


def bind_delete_key(table: QTableView, delete: Callable[[], None]) -> None:
    """Calls ``delete`` when Supr is pressed on ``table``, as the page's «Eliminar» button
    does; ``delete`` asks for confirmation and ignores no selection."""
    table.installEventFilter(_DeleteKeyFilter(table, delete))


def fit_rows(table: QTableView) -> None:
    """Makes ``table`` exactly as tall as its rows, for a short table inside a page that
    scrolls as a whole. Measured from the size hints, so it also works before the table
    is first shown."""
    rows = table.model().rowCount() * table.verticalHeader().defaultSectionSize()
    height = table.horizontalHeader().sizeHint().height() + rows
    table.setFixedHeight(height + 2 * table.frameWidth())
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)


class _LinkRows(QStyledItemDelegate):
    """Makes each row of a table a link: it lights up whole under the mouse, as every row
    that does something, and a click on it calls ``open_row`` (the table has nothing to
    choose, so one click is enough, as on the Dashboard's category rows)."""

    def __init__(self, table: QTableView, open_row: Callable[[int], None]) -> None:
        super().__init__(table)
        self._table = table
        self._open_row = open_row
        self.hovered_row = -1
        table.viewport().installEventFilter(self)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        if index.row() == self.hovered_row:
            painter.fillRect(option.rect, QColor(active_theme().hover))
        super().paint(painter, option, index)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.MouseMove and isinstance(event, QMouseEvent):
            self._hover(self._table.indexAt(event.position().toPoint()).row())
        elif event.type() == QEvent.Type.Leave:
            self._hover(-1)
        elif (
            event.type() == QEvent.Type.MouseButtonRelease
            and isinstance(event, QMouseEvent)
            and event.button() == Qt.MouseButton.LeftButton
        ):
            row = self._table.indexAt(event.position().toPoint()).row()
            if row >= 0:
                self._open_row(row)
                return True
        return False

    def _hover(self, row: int) -> None:
        if row != self.hovered_row:
            self.hovered_row = row
            self._table.viewport().update()


def make_link_rows(table: QTableView, open_row: Callable[[int], None], tip: str) -> None:
    """Turns the rows of a report table into links to ``open_row(row)``, following the
    row rules: they light up under the mouse and open with one click."""
    table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    table.setMouseTracking(True)
    table.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
    table.setToolTip(tip)
    table.setItemDelegate(_LinkRows(table, open_row))
