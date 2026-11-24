"""A table in a narrow window drops what matters least instead of scrolling sideways,
and shows it back when there is room (widgets/tables/table.py)."""

from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QHeaderView

from nodus.ui.widgets.tables.table import (
    drop_columns_when_narrow,
    record_table,
    set_column_shown,
)

NAME, COUNT, TOTAL, USUAL = range(4)


def make(qtbot):
    model = QStandardItemModel(3, 4)
    for row in range(3):
        texts = ["Supermercado", "12 movimientos", "$ 1.234.567,89", "Supermercado y comida"]
        for column, text in enumerate(texts):
            model.setItem(row, column, QStandardItem(text))
    table = record_table(model, NAME)
    qtbot.addWidget(table)
    table.show()
    drop_columns_when_narrow(table, (USUAL, TOTAL))
    return table


def scrolls(table) -> bool:
    return table.horizontalScrollBar().maximum() > 0


def test_drops_columns_in_order_while_they_do_not_fit(qtbot):
    table = make(qtbot)

    table.resize(1000, 300)
    assert not any(table.isColumnHidden(c) for c in range(4))
    table.resize(330, 300)
    assert table.isColumnHidden(USUAL)
    assert not table.isColumnHidden(COUNT)
    assert not scrolls(table)


def test_shows_them_back_when_there_is_room(qtbot):
    table = make(qtbot)
    table.resize(250, 300)
    table.resize(1000, 300)

    assert not any(table.isColumnHidden(c) for c in range(4))
    assert table.horizontalHeader().sectionResizeMode(NAME) == QHeaderView.ResizeMode.Stretch


def test_a_column_the_page_hides_stays_hidden(qtbot):
    table = make(qtbot)
    set_column_shown(table, USUAL, False)

    table.resize(250, 300)
    table.resize(1000, 300)

    assert table.isColumnHidden(USUAL)
    set_column_shown(table, USUAL, True)
    assert not table.isColumnHidden(USUAL)
