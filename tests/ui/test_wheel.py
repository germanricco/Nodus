"""The wheel scrolls one thing at a time: a list inside a page keeps it, and a value
control without the focus lets the page have it."""

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

DOWN = -120  # one notch of the wheel, away from the user


def turn(widget: QWidget, delta: int = DOWN) -> QWheelEvent:
    """One notch of the wheel over the middle of ``widget``.

    Qt passes a real wheel event up to the parents, and so to the page, while it is not
    accepted; one sent from a test stays with ``widget``. So whether the page would move
    is read from the event: still accepted means someone kept it."""
    center = QPointF(widget.rect().center())
    event = QWheelEvent(
        center,
        QPointF(widget.mapToGlobal(center.toPoint())),
        QPoint(),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(widget, event)
    return event


@pytest.fixture
def page(qtbot, theme_manager):
    """A page that scrolls, as every page of Nodus, with a table and a list in it."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    content = QWidget()
    layout = QVBoxLayout(content)
    area.table = QTableWidget(0, 1)
    area.table.setFixedHeight(120)
    area.combo = QComboBox()
    area.combo.addItems(["Uno", "Dos", "Tres"])
    layout.addWidget(area.table)
    layout.addWidget(area.combo)
    layout.addSpacing(2000)  # taller than the window: the page scrolls
    area.setWidget(content)
    area.resize(400, 400)
    qtbot.addWidget(area)
    area.show()
    qtbot.waitExposed(area)
    return area


def fill(table: QTableWidget, rows: int) -> None:
    """``rows`` rows; the table works out how far it scrolls on the next loop turn."""
    table.setRowCount(rows)
    QApplication.processEvents()


def test_a_list_at_its_end_does_not_scroll_the_page(page):
    fill(page.table, 50)
    bar = page.table.verticalScrollBar()
    bar.setValue(bar.maximum())

    event = turn(page.table.viewport())

    assert bar.value() == bar.maximum()
    assert event.isAccepted()  # kept: the page does not get it


def test_a_list_scrolls_itself_first(page):
    fill(page.table, 50)

    turn(page.table.viewport())

    assert page.table.verticalScrollBar().value() > 0
    assert page.verticalScrollBar().value() == 0


def test_a_list_that_fits_lets_the_page_scroll(page):
    fill(page.table, 1)

    event = turn(page.table.viewport())

    assert not event.isAccepted()  # left for the page


def test_a_list_of_options_without_focus_scrolls_the_page_instead(page):
    turn(page.combo)

    assert page.combo.currentIndex() == 0
    assert page.verticalScrollBar().value() > 0


def test_a_list_of_options_with_focus_changes(page):
    page.combo.setFocus()
    assert page.combo.hasFocus()

    turn(page.combo)

    assert page.combo.currentIndex() == 1


def test_a_list_of_options_outside_a_page_works_as_always(qtbot, theme_manager):
    combo = QComboBox()
    combo.addItems(["Uno", "Dos"])
    qtbot.addWidget(combo)
    combo.show()

    turn(combo)

    assert combo.currentIndex() == 1
