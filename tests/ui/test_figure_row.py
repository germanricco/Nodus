"""Figure tiles that wrap onto more rows instead of being cut."""

import pytest
from PySide6.QtWidgets import QLabel

from nodus.ui.pages.dashboard_cards import FigureTile
from nodus.ui.widgets.figure_row import FigureRow, balanced_columns


@pytest.mark.parametrize(
    ("count", "fits", "columns"), [(5, 5, 5), (5, 3, 3), (5, 4, 3), (5, 2, 2), (4, 3, 2), (3, 0, 1)]
)
def test_rows_are_spread_evenly(count, fits, columns):
    assert balanced_columns(count, fits) == columns


@pytest.fixture
def figures(qtbot) -> FigureRow:
    row = FigureRow()
    for caption in ("Objetivo", "Ahorrado", "Falta", "Por mes", "Ritmo"):
        row.add_tile(FigureTile(caption, QLabel("US$ 12.345.678,90"), large=True))
    qtbot.addWidget(row)
    row.show()
    return row


def test_wide_enough_they_share_one_row(figures, qtbot):
    figures.resize(5 * figures.tiles[0].sizeHint().width() + 100, 100)
    qtbot.waitUntil(lambda: figures.columns() == 5)


def test_narrow_they_wrap_and_none_is_cut(figures, qtbot):
    figures.resize(2 * figures.tiles[0].sizeHint().width() + 40, 100)

    qtbot.waitUntil(lambda: figures.columns() == 2)
    figures.layout().activate()
    for tile in figures.tiles:
        assert tile.width() >= tile.minimumSizeHint().width()


def test_a_hidden_tile_takes_no_place(figures, qtbot):
    figures.resize(5 * figures.tiles[0].sizeHint().width() + 100, 100)
    figures.tiles[2].hide()

    figures.relayout()

    assert figures.columns() == 4
