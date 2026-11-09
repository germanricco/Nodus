"""Read-only tables of records, as the transactions and payees pages show them."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QAbstractItemModel, QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView


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
