"""Read-only tables of records, as the transactions and payees pages show them."""

from __future__ import annotations

from PySide6.QtCore import QAbstractItemModel, Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView


def record_table(model: QAbstractItemModel, stretch_column: int) -> QTableView:
    """A table of whole-row selection, without grid or editing, whose columns fit their
    content except ``stretch_column``, which takes the remaining width."""
    table = QTableView()
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
    for column in range(model.columnCount()):
        header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(stretch_column, QHeaderView.ResizeMode.Stretch)
    return table


def fit_rows(table: QTableView) -> None:
    """Makes ``table`` exactly as tall as its rows, for a short table inside a page that
    scrolls as a whole. Measured from the size hints, so it also works before the table
    is first shown."""
    rows = table.model().rowCount() * table.verticalHeader().defaultSectionSize()
    height = table.horizontalHeader().sizeHint().height() + rows
    table.setFixedHeight(height + 2 * table.frameWidth())
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
