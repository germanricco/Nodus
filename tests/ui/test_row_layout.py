"""Every list stacks rows of the same heights (``RowRole``), each with what it holds
centered, so lists read alike on every page."""

from PySide6.QtWidgets import QLabel, QWidget

from nodus.ui.theme.design import RowRole, RowSpace
from nodus.ui.widgets.tables.row_layout import row_layout, row_lines, row_list


def two_line_row(qtbot, role: RowRole) -> tuple[QWidget, QLabel, QLabel]:
    row = QWidget()
    qtbot.addWidget(row)
    layout = row_layout(row, role)
    lines = row_lines()
    title, detail = QLabel("Título"), QLabel("Detalle")
    lines.addWidget(title)
    lines.addWidget(detail)
    layout.addLayout(lines)
    row.resize(300, row.sizeHint().height())
    row.show()
    return row, title, detail


def test_a_row_takes_the_height_of_its_role(qtbot):
    for role in RowRole:
        row = QWidget()
        qtbot.addWidget(row)
        row_layout(row, role).addWidget(QLabel("Texto"))
        assert row.sizeHint().expandedTo(row.minimumSize()).height() == role


def test_a_title_and_its_detail_stay_together_in_the_middle(qtbot):
    row, title, detail = two_line_row(qtbot, RowRole.DOUBLE)
    assert title.geometry().bottom() + 1 == detail.geometry().top()
    above = title.geometry().top()
    below = row.height() - detail.geometry().bottom() - 1
    assert abs(above - below) <= 1


def test_every_row_has_the_same_room_at_its_sides(qtbot):
    row, title, _detail = two_line_row(qtbot, RowRole.DOUBLE)
    assert title.geometry().left() == RowSpace.SIDE


def test_an_indented_row_moves_right(qtbot):
    row = QWidget()
    qtbot.addWidget(row)
    layout = row_layout(row, RowRole.SIDEBAR, indent=12)
    assert layout.contentsMargins().left() == RowSpace.SIDE + 12


def test_a_line_inside_a_taller_row_has_no_height_of_its_own(qtbot):
    row = QWidget()
    qtbot.addWidget(row)
    layout = row_layout(row, None)
    assert row.minimumHeight() == 0
    assert layout.contentsMargins().top() == layout.contentsMargins().bottom() == 0


def test_the_rows_of_a_list_touch():
    assert row_list().spacing() == 0
