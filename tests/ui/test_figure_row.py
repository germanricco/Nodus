"""Figure tiles that wrap onto more rows instead of being cut."""

import pytest
from PySide6.QtWidgets import QLabel

from nodus.ui.theme.design import Layout
from nodus.ui.widgets.change_badge import ChangeBadge
from nodus.ui.widgets.figure_row import FigureRow, balanced_columns
from nodus.ui.widgets.figure_tile import FigureTile


@pytest.mark.parametrize(
    ("count", "fits", "columns"), [(5, 5, 5), (5, 3, 3), (5, 4, 3), (5, 2, 2), (4, 3, 2), (3, 0, 1)]
)
def test_rows_are_spread_evenly(count, fits, columns):
    assert balanced_columns(count, fits) == columns


def room(tile: FigureTile) -> int:
    """The width a tile asks for in its row: its figure's, or the comfortable minimum."""
    return max(tile.sizeHint().width(), Layout.FIGURE_TILE_MIN_WIDTH)


@pytest.fixture
def figures(qtbot) -> FigureRow:
    row = FigureRow()
    for caption in ("Objetivo", "Ahorrado", "Falta", "Por mes", "Ritmo"):
        row.add_tile(FigureTile(caption, QLabel("US$ 12.345.678,90")))
    qtbot.addWidget(row)
    row.show()
    return row


def test_wide_enough_they_share_one_row(figures, qtbot):
    figures.resize(5 * room(figures.tiles[0]) + 100, 100)
    qtbot.waitUntil(lambda: figures.columns() == 5)


def test_narrow_they_wrap_and_none_is_cut(figures, qtbot):
    figures.resize(2 * room(figures.tiles[0]) + 40, 100)

    qtbot.waitUntil(lambda: figures.columns() == 2)
    figures.layout().activate()
    for tile in figures.tiles:
        assert tile.width() >= tile.minimumSizeHint().width()


def test_a_hidden_tile_takes_no_place(figures, qtbot):
    figures.resize(5 * room(figures.tiles[0]) + 100, 100)
    figures.tiles[2].hide()

    figures.relayout()

    assert figures.columns() == 4


def test_a_badge_beside_its_figure_wraps_the_row_rather_than_being_cut(qtbot):
    """The widest case: a long figure with a three-digit change beside it."""
    row = FigureRow()
    qtbot.addWidget(row)
    badge = ChangeBadge()
    tiles = [FigureTile("Movimientos", QLabel("12")),
             FigureTile("Este mes", QLabel("$ 12.345.678,90"), badge, badge_beside=True),
             FigureTile("Promedio por mes", QLabel("$ 12.345.678,90"))]  # fmt: skip
    for tile in tiles:
        row.add_tile(tile)
    badge.set_change(3.0)
    assert badge.text() == "↗ 300 %"
    row.show()
    narrow = 2 * tiles[1].sizeHint().width() + FigureRow.SPACING

    row.resize(narrow, 100)
    row.relayout()
    row.layout().activate()

    assert row.columns() == 2
    value = tiles[1].value
    assert value.width() >= value.sizeHint().width()
    assert badge.width() >= badge.sizeHint().width()
    assert badge.geometry().left() > value.geometry().right()  # beside, not under


def test_short_figures_still_wrap_before_their_boxes_get_cramped(qtbot):
    """Three boxes whose figures would fit in very little room still each keep a
    comfortable width: below it they go onto more rows."""
    row = FigureRow()
    qtbot.addWidget(row)
    for caption in ("A", "B", "C"):
        row.add_tile(FigureTile(caption, QLabel("1")))
    row.show()

    row.resize(3 * Layout.FIGURE_TILE_MIN_WIDTH + 2 * FigureRow.SPACING, 200)
    assert row.columns() == 3
    row.resize(3 * Layout.FIGURE_TILE_MIN_WIDTH, 200)
    assert row.columns() == 2
