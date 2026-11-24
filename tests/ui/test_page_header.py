"""A page's header never squeezes: its filters go under the title when the row has no
room, and a title too long for it ends in «…» (pages/base/page.py)."""

import pytest
from PySide6.QtWidgets import QLineEdit, QWidget

from nodus.ui.pages.base.page import Page
from nodus.ui.theme.design import Layout

WIDE, NARROW = 1000, 420


@pytest.fixture
def page(qtbot) -> Page:
    page = Page("Beneficiarios")
    qtbot.addWidget(page)
    page.add_header_filter(fixed(240))
    page.add_header_filter(QLineEdit("Buscar beneficiario…"))
    page.add_header_button("Agregar beneficiario", primary=True)
    bar = QWidget()
    page.set_selection_bar(bar)
    page.show()
    return page


def fixed(width: int) -> QWidget:
    widget = QWidget()
    widget.setFixedWidth(width)
    return widget


def resized(qtbot, page: Page, width: int) -> None:
    page.resize(width, 600)
    qtbot.waitUntil(
        lambda: page.header.width() == width - page.layout().contentsMargins().left() * 2
    )


def test_everything_in_one_row_while_it_fits(qtbot, page):
    resized(qtbot, page, WIDE)

    assert not page.header.two_rows()
    assert page.header.height() == Layout.HEADER_HEIGHT


def test_the_filters_go_under_the_title_when_the_row_has_no_room(qtbot, page):
    resized(qtbot, page, NARROW)

    assert page.header.two_rows()
    assert page.header.height() > Layout.HEADER_HEIGHT
    assert page.title_label.width() >= page.title_label.sizeHint().width()  # not cut
    assert page.header.filters.geometry().top() > page.title_label.geometry().bottom()


def test_and_come_back_beside_it_when_there_is_room_again(qtbot, page):
    resized(qtbot, page, NARROW)
    resized(qtbot, page, WIDE)

    assert not page.header.two_rows()
    assert page.header.height() == Layout.HEADER_HEIGHT


def test_choosing_rows_moves_nothing_below(qtbot, page):
    resized(qtbot, page, NARROW)
    height = page.header.height()

    page.show_selection_bar(True)
    qtbot.wait(10)
    assert page.header.height() == height
    page.show_selection_bar(False)
    qtbot.wait(10)
    assert page.header.height() == height


def test_without_filters_the_title_gives_way(qtbot):
    page = Page("Supermercado y comida, la categoría de siempre")
    qtbot.addWidget(page)
    page.add_header_button("Editar")
    page.add_header_button("Unir con…")
    page.show()
    resized(qtbot, page, NARROW)

    assert not page.header.two_rows()
    assert page.header.height() == Layout.HEADER_HEIGHT
    assert page.title_label.width() < page.title_label.sizeHint().width()
    assert page.title_label.toolTip() == "Supermercado y comida, la categoría de siempre"


def test_a_new_title_is_in_its_tooltip(qtbot):
    page = Page("")
    qtbot.addWidget(page)

    page.set_title("Ahorro en dólares")

    assert page.title_label.toolTip() == "Ahorro en dólares"
