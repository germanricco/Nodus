"""The bar that takes a page's header while several rows are chosen."""

import pytest

from nodus.ui.widgets.tables.selection_bar import SelectionBar


@pytest.mark.parametrize("detail", ["", "Gastos $ 70.500,00"])
def test_its_buttons_keep_their_size_with_or_without_a_detail(qtbot, detail):
    bar = SelectionBar()
    qtbot.addWidget(bar)
    merge = bar.add_action("Unir…", lambda: None)
    bar.set_count(2, detail)
    bar.resize(1000, bar.sizeHint().height())
    bar.show()
    bar.layout().activate()

    for button in (merge, bar.clear_button):
        assert button.width() <= button.sizeHint().width()
