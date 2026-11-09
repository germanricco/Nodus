"""Rows that can be clicked or have a menu light up under the mouse, without being chosen."""

from factories import ars, expense_draft
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest

from nodus.ui.navigation import PageId
from nodus.ui.pages.accounts_page import AccountRow


def background(widget, point: QPoint) -> str:
    return widget.grab().toImage().pixelColor(point).name()


def test_an_account_row_lights_up_under_the_mouse(window, theme_manager, pesos):
    window.show_page(PageId.ACCOUNTS)
    row = next(r for r in window.page(PageId.ACCOUNTS).findChildren(AccountRow) if r.isVisible())
    edge = QPoint(2, row.height() // 2)  # inside the row, left of its content
    assert background(row, edge) != theme_manager.theme.hover

    QTest.mouseMove(row, row.rect().center())

    assert row.underMouse()
    assert background(row, edge) == QColor(theme_manager.theme.hover).name()


def test_a_table_row_lights_up_but_is_not_chosen(window, theme_manager, services, pesos):
    services.transactions.create(expense_draft(services, pesos.id, ars("10")))
    window.show_page(PageId.TRANSACTIONS)
    table = window.page(PageId.TRANSACTIONS).table
    cell = table.visualRect(table.model().index(0, 2))

    QTest.mouseMove(table.viewport(), cell.center())

    assert table.hovered_row == 0
    assert table.selected_rows() == []
    color = table.viewport().grab().toImage().pixelColor(cell.center().x(), cell.top() + 2)
    assert color.name() == QColor(theme_manager.theme.hover).name()
