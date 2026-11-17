"""Reordering rows by dragging their handle."""

import pytest
from dragging import send_drop
from PySide6.QtCore import QMimeData
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QFrame, QLabel

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


class TestFamily:
    """Lists of one family take each other's rows; an empty one is a place to drop."""

    def family_list(self, qtbot, keys: list[str], family: str | None = "accounts"):
        widget = ReorderableList(family=family)
        for key in keys:
            label = QLabel(key)
            label.setFixedHeight(40)
            widget.add_row(key, label)
        qtbot.addWidget(widget)
        widget.resize(300, 120)
        widget.show()
        return widget

    def test_a_row_from_the_family_is_received_at_its_gap(self, qtbot):
        source = self.family_list(qtbot, ["a", "b"])
        target = self.family_list(qtbot, ["x", "y"])

        with (
            qtbot.assertNotEmitted(target.order_changed),
            qtbot.waitSignal(target.row_received) as signal,
        ):
            assert send_drop(target, source.mime_data(1), middle_of(target, 1) - 1)

        assert signal.args == ["b", 1]

    @pytest.mark.parametrize("family", ["categories", None])
    def test_another_family_or_none_is_refused(self, qtbot, family):
        source = self.family_list(qtbot, ["a"])
        target = self.family_list(qtbot, ["x"], family)

        with qtbot.assertNotEmitted(target.row_received):
            assert not send_drop(target, source.mime_data(0), 0)

    def test_an_empty_list_shows_its_place_and_takes_a_row(self, qtbot):
        source = self.family_list(qtbot, ["a"])
        empty = self.family_list(qtbot, [])
        empty.set_placeholder("Arrastra una aquí")
        assert not empty.placeholder.isHidden()

        with qtbot.waitSignal(empty.row_received) as signal:
            assert send_drop(empty, source.mime_data(0), 10)

        assert signal.args == ["a", 0]
        assert not empty.placeholder.property("active")  # lit only while over it

    def test_the_place_goes_once_there_are_rows(self, qtbot):
        widget = self.family_list(qtbot, [])
        widget.set_placeholder("Arrastra una aquí")

        widget.add_row("a", QLabel("a"))

        assert widget.placeholder.isHidden()
