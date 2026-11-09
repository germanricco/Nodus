"""Helpers to use row menus in tests without opening them, and to double-click rows."""

from collections.abc import Sequence

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QTableView, QWidget

from nodus.ui.widgets.row_actions import RowAction


def texts(actions: Sequence[RowAction]) -> list[str]:
    return [action.text for action in actions]


def main_action(actions: Sequence[RowAction]) -> str | None:
    """The text of the row's main action, the bold one in its menu."""
    return next((action.text for action in actions if action.default), None)


def run_action(actions: Sequence[RowAction], text: str) -> None:
    """Does what choosing the item ``text`` in the menu does."""
    action = next(action for action in actions if action.text == text)
    assert action.enabled, f"«{text}» is disabled"
    action.callback()


def double_click(widget: QWidget) -> None:
    """A double click on ``widget``, left of its content (on its own background)."""
    QTest.mouseDClick(widget, Qt.MouseButton.LeftButton, pos=QPoint(2, widget.height() // 2))


def double_click_row(table: QTableView, row: int, column: int = 2) -> None:
    """A double click on a cell of ``row``, away from the check box and the «⋯»."""
    center = table.visualRect(table.model().index(row, column)).center()
    QTest.mouseDClick(table.viewport(), Qt.MouseButton.LeftButton, pos=center)
