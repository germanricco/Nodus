"""The one grid of cards: columns from the width alone, at most three."""

import pytest

from nodus.ui.theme.design import Layout
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.card_grid import CardGrid, grid_columns


@pytest.mark.parametrize(
    ("width", "columns"),
    [(436, 1), (616, 1), (776, 2), (956, 2), (1100, 2), (1140, 3), (1600, 3)],
)
def test_the_width_alone_sets_the_columns(width, columns):
    assert grid_columns(width) == columns


def test_never_more_than_the_maximum():
    assert grid_columns(10_000) == Layout.GRID_MAX_COLUMNS


def test_a_set_of_cards_that_read_together_shares_the_whole_width(qtbot):
    grid = CardGrid(most_columns=2)
    qtbot.addWidget(grid)
    cards = [Card("Por categoría"), Card("Por beneficiario")]
    grid.set_cards(cards)
    grid.show()
    grid.resize(1600, 400)

    qtbot.waitUntil(lambda: grid.columns() == 2)
    assert cards[1].geometry().right() == grid.width() - 1


@pytest.fixture
def grid(qtbot) -> CardGrid:
    grid = CardGrid()
    qtbot.addWidget(grid)
    grid.set_cards([Card(f"Meta {n}") for n in range(5)])
    grid.show()
    return grid


def test_the_cards_reflow_with_the_width(grid, qtbot):
    grid.resize(1600, 400)
    qtbot.waitUntil(lambda: grid.columns() == 3)
    grid.resize(776, 400)
    qtbot.waitUntil(lambda: grid.columns() == 2)


def test_cards_of_a_row_share_its_width_and_height(grid, qtbot):
    grid.resize(776, 600)
    qtbot.waitUntil(lambda: grid.columns() == 2)
    grid.layout().activate()
    first, second = grid.cards[0], grid.cards[1]
    assert abs(first.width() - second.width()) <= 1
    assert first.height() == second.height()
    assert first.y() == second.y()


def test_new_cards_replace_the_old_ones(grid, qtbot):
    old = grid.cards[0]
    grid.set_cards([Card("Única")])
    assert grid.cards[0] is not old and len(grid.cards) == 1


def test_a_lone_card_is_as_wide_as_one_of_a_full_row(qtbot):
    """The columns come from the width, not from the cards: a section with one card
    shows it as wide as a section with two, at the same width."""
    grids = []
    for count in (2, 1):
        grid = CardGrid()
        qtbot.addWidget(grid)
        grid.set_cards([Card(f"Meta {n}") for n in range(count)])
        grid.resize(776, 300)
        grid.show()
        qtbot.waitUntil(lambda grid=grid: grid.columns() == 2)
        grid.layout().activate()
        grids.append(grid)
    pair, lone = grids
    assert abs(lone.cards[0].width() - pair.cards[0].width()) <= 1
