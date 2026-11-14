"""Reordering rows by dragging their handle."""

import pytest
from PySide6.QtCore import QMimeData, QPointF, Qt
from PySide6.QtGui import QDrag, QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QFrame, QLabel

from nodus.ui.widgets.reorderable_list import ROW_MIME_TYPE, ReorderableList, drag_pixmap

KEYS = ["a", "b", "c"]


@pytest.fixture
def rows(qtbot) -> ReorderableList:
    widget = ReorderableList()
    for key in KEYS:
        label = QLabel(key)
        label.setFixedHeight(40)
        widget.add_row(key, label)
    qtbot.addWidget(widget)
    widget.resize(300, 120)
    widget.show()
    qtbot.waitExposed(widget)
    return widget


def middle_of(rows: ReorderableList, index: int) -> int:
    return rows.rows()[index].geometry().center().y()


def send_drop(rows: ReorderableList, mime: QMimeData, y: float) -> bool:
    """Drags ``mime`` over ``rows`` and drops it at height ``y``, as the mouse would;
    returns whether the list took the drop."""
    point = QPointF(20, y)
    args = (Qt.DropAction.MoveAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier(0))
    enter = QDragEnterEvent(point, *args)
    QApplication.sendEvent(rows, enter)
    QApplication.sendEvent(rows, QDragMoveEvent(point, *args))
    drop = QDropEvent(point, *args)
    QApplication.sendEvent(rows, drop)
    return drop.isAccepted()


def test_insertion_index_follows_the_middle_of_each_row(rows):
    assert rows.insertion_index(0) == 0
    assert rows.insertion_index(middle_of(rows, 0) + 1) == 1
    assert rows.insertion_index(middle_of(rows, 2) + 1) == 3


@pytest.mark.parametrize(
    ("source", "target", "order"),
    [(0, 3, ["b", "c", "a"]), (2, 0, ["c", "a", "b"]), (0, 2, ["b", "a", "c"])],
)
def test_move_emits_the_new_order(qtbot, rows, source, target, order):
    with qtbot.waitSignal(rows.order_changed) as signal:
        rows.move(source, target)

    assert signal.args == [order]


@pytest.mark.parametrize("target", [1, 2])
def test_dropping_a_row_beside_itself_changes_nothing(qtbot, rows, target):
    with qtbot.assertNotEmitted(rows.order_changed):
        rows.move(1, target)


def test_dropping_the_first_row_at_the_end(qtbot, rows):
    with qtbot.waitSignal(rows.order_changed) as signal:
        accepted = send_drop(rows, rows.mime_data(0), rows.height() - 1)

    assert accepted
    assert signal.args == [["b", "c", "a"]]
    assert rows.findChild(QFrame, "DropIndicator").isHidden()


def test_rows_of_another_list_are_refused(qtbot, rows):
    other = ReorderableList()
    other.add_row("x", QLabel("x"))
    qtbot.addWidget(other)

    with qtbot.assertNotEmitted(rows.order_changed):
        assert not send_drop(rows, other.mime_data(0), 0)
    foreign = QMimeData()
    foreign.setText("not a row")
    assert not send_drop(rows, foreign, 0)
    assert ROW_MIME_TYPE not in foreign.formats()


def test_the_dragged_picture_keeps_the_background_of_the_row(rows):
    """Not transparent, which Windows draws black and hides the line where it lands."""
    rows.setStyleSheet("background: white;")
    picture = drag_pixmap(rows.rows()[1]).toImage()

    middle = picture.pixelColor(picture.width() // 2, picture.height() // 2)
    assert middle.alpha() > 200
    assert middle.lightness() > 200


def test_the_row_fades_while_dragged_and_comes_back(rows, monkeypatch):
    row = rows.rows()[0]
    seen = []
    monkeypatch.setattr(
        QDrag, "exec", lambda _drag, _action: seen.append(row.graphicsEffect().opacity())
    )

    row.start_drag()

    assert seen[0] < 1
    assert row.graphicsEffect() is None
