"""Helpers to use row menus in tests without opening them, and to double-click rows."""

from collections.abc import Sequence

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QTableView, QWidget

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


def double_click(widget: QWidget, pos: QPoint | None = None) -> None:
    """A double click on ``widget`` (by default left of its content, on its own
    background), sent to it directly.

    ``QTest.mouseDClick`` would leave Qt's mouse state behind when the double click
    opens another page: the hidden widget keeps the mouse, and later tests' moves never
    reach their rows.
    """
    point = QPointF(pos if pos is not None else QPoint(2, widget.height() // 2))
    event = QMouseEvent(
        QEvent.Type.MouseButtonDblClick,
        point,
        QPointF(widget.mapToGlobal(point)),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, event)


def double_click_row(table: QTableView, row: int, column: int = 2) -> None:
    """A double click on a cell of ``row``, away from the check box and the «⋯»."""
    double_click(table.viewport(), table.visualRect(table.model().index(row, column)).center())
