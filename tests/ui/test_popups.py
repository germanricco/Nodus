"""Every list and menu that opens over a page leaves room around its options.

The spacing comes from ``Popup`` (design.py) through the stylesheet, so these tests open
the real popups and measure them, and change ``Popup.PADDING`` to see every list follow.
"""

import pytest
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QVBoxLayout,
    QWidget,
)

from nodus.models.payee import Payee
from nodus.models.transaction import TransactionType
from nodus.ui.dialogs.transaction_dialog import TransactionDialog
from nodus.ui.navigation import PageId
from nodus.ui.theme import design
from nodus.ui.theme.design import Popup
from nodus.ui.theme.theme import ThemeMode
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.row_actions import RowAction, build_menu
from nodus.ui.widgets.selectors import PayeeComboBox

BORDER = 1


@pytest.fixture(params=[ThemeMode.LIGHT, ThemeMode.DARK], ids=["light", "dark"])
def theme(request, qapp) -> ThemeManager:
    return ThemeManager(qapp, request.param)


def make_dialog(qtbot, services, event_bus, theme) -> TransactionDialog:
    dialog = TransactionDialog(services, event_bus, theme)
    qtbot.addWidget(dialog)
    dialog.show()
    return dialog


def open_list(qtbot, combo: QComboBox) -> QAbstractItemView:
    combo.showPopup()
    view = combo.view()
    qtbot.waitUntil(view.isVisible)
    QApplication.processEvents()
    return view


def bottom_gap(view: QAbstractItemView) -> int:
    """From the bottom of the last option to the list's outer edge, with the list
    scrolled to its end."""
    view.scrollToBottom()
    QApplication.processEvents()
    last = view.model().index(view.model().rowCount() - 1, 0)
    bottom = view.viewport().y() + view.visualRect(last).bottom() + 1
    return view.height() - bottom


def top_gap(view: QAbstractItemView) -> int:
    view.scrollToTop()
    QApplication.processEvents()
    first = view.model().index(0, 0)
    return view.viewport().y() + view.visualRect(first).top()


def assert_spaced(view: QAbstractItemView, padding: int = Popup.PADDING) -> None:
    """Exactly the frame's padding at both ends: too little touches the border, too
    much reads as a different kind of list."""
    assert top_gap(view) == padding + BORDER
    assert bottom_gap(view) == padding + BORDER


def option_height(view: QAbstractItemView, row: int = 0) -> int:
    return view.visualRect(view.model().index(row, 0)).height()


def assert_options_padded(view: QAbstractItemView) -> None:
    text = view.fontMetrics().height()
    assert option_height(view) >= text + 2 * Popup.LIST_ITEM_PADDING[0]


def test_installments_list_leaves_room_after_its_last_option(
    qtbot, services, event_bus, pesos, theme
):
    dialog = make_dialog(qtbot, services, event_bus, theme)

    view = open_list(qtbot, dialog.installment_fields.count_input)

    assert_spaced(view)
    assert_options_padded(view)


def test_installments_separator_is_a_thin_line_not_an_empty_option(
    qtbot, services, event_bus, pesos, theme
):
    dialog = make_dialog(qtbot, services, event_bus, theme)
    combo = dialog.installment_fields.count_input
    view = open_list(qtbot, combo)

    separator = combo.findText("Otra cantidad…") - 1

    assert option_height(view, separator) == Popup.DIVIDER_HEIGHT
    assert option_height(view, separator) < option_height(view)


def test_a_long_category_list_scrolls_to_a_spaced_end(qtbot, services, event_bus, pesos, theme):
    dialog = make_dialog(qtbot, services, event_bus, theme)
    combo = dialog.category_input
    combo.setMaxVisibleItems(4)  # shorter than the list, so it scrolls

    view = open_list(qtbot, combo)

    assert view.verticalScrollBar().maximum() > 0
    assert_spaced(view)


def test_a_one_option_list_is_spaced_too(qtbot, theme):
    # Inside a window, as every combo box of the app: Qt leaves the list of a combo box
    # that is a window by itself out of the stylesheet.
    host = QWidget()
    qtbot.addWidget(host)
    combo = PayeeComboBox()
    QVBoxLayout(host).addWidget(combo)
    combo.set_payees([Payee(1, "Coto")])
    host.show()

    view = open_list(qtbot, combo)

    assert view.model().rowCount() == 1
    assert_spaced(view)
    assert_options_padded(view)


def test_transactions_filter_list_is_spaced(qtbot, window):
    window.show_page(PageId.TRANSACTIONS)
    page = window.page(PageId.TRANSACTIONS)

    view = open_list(qtbot, page.type_filter)

    assert_spaced(view)
    assert_options_padded(view)


def test_payee_suggestions_are_spaced(qtbot, services, event_bus, pesos, theme):
    for name in ["Coto", "Carrefour", "Cine"]:
        services.payees.create(name)
    dialog = make_dialog(qtbot, services, event_bus, theme)

    qtbot.keyClicks(dialog.payee_input.line_edit, "c")
    popup = dialog.payee_input.names.completer.popup()
    qtbot.waitUntil(popup.isVisible)

    assert_spaced(popup)
    assert_options_padded(popup)


def test_suggestions_that_fit_need_no_scroll_bar(qtbot, services, event_bus, pesos, theme):
    """QCompleter sizes its list without the ListPopup padding; NameCompleter makes up
    for it, or a list of six would scroll."""
    for number in range(6):
        services.payees.create(f"Comercio {number}")
    dialog = make_dialog(qtbot, services, event_bus, theme)

    qtbot.keyClicks(dialog.payee_input.line_edit, "comercio")
    popup = dialog.payee_input.names.completer.popup()
    qtbot.waitUntil(popup.isVisible)

    qtbot.waitUntil(lambda: not popup.verticalScrollBar().isVisible(), timeout=1000)
    assert_spaced(popup)


def test_menu_actions_take_the_menu_padding(qtbot, window):
    menu = build_menu(window, [RowAction("Editar", lambda: None), RowAction("Ver", lambda: None)])
    menu.popup(window.mapToGlobal(window.rect().center()))
    qtbot.waitUntil(menu.isVisible)

    first = menu.actionGeometry(menu.actions()[0])
    last = menu.actionGeometry(menu.actions()[-1])

    assert first.top() >= Popup.PADDING + BORDER
    assert menu.height() - (last.bottom() + 1) >= Popup.PADDING + BORDER
    text = menu.fontMetrics().height()
    assert first.height() >= text + 2 * Popup.MENU_ITEM_PADDING[0]
    menu.close()


def test_one_value_spaces_every_list(qtbot, monkeypatch, services, event_bus, pesos):
    """Changing Popup.PADDING alone moves the edge of every list: it is the one value."""
    wider = Popup.PADDING + 8
    monkeypatch.setattr(design.Popup, "PADDING", wider)
    theme = ThemeManager(QApplication.instance(), ThemeMode.LIGHT)
    dialog = make_dialog(qtbot, services, event_bus, theme)

    for combo in (dialog.installment_fields.count_input, dialog.category_input):
        view = open_list(qtbot, combo)
        assert_spaced(view, wider)
        combo.hidePopup()


def test_options_with_a_color_dot_are_as_tall_as_plain_ones(qtbot, window):
    """Qt makes a row with an icon taller; the category filter must not read looser."""
    window.show_page(PageId.TRANSACTIONS)
    page = window.page(PageId.TRANSACTIONS)
    plain = open_list(qtbot, page.type_filter)
    plain_height = option_height(plain)
    page.type_filter.hidePopup()

    categories = open_list(qtbot, page.category_filter)
    dotted = next(
        row
        for row in range(categories.model().rowCount())
        if not page.category_filter.itemIcon(row).isNull()
    )

    assert option_height(categories, dotted) == plain_height


def test_the_scrolling_category_filter_ends_like_every_other_list(qtbot, services, window):
    """The longest list: scrolling by whole options left part of a row empty at its end."""
    for index in range(12):
        services.categories.create(f"Extra {index}", TransactionType.EXPENSE, "#3366cc")
    window.show_page(PageId.TRANSACTIONS)
    page = window.page(PageId.TRANSACTIONS)
    page.refresh()

    view = open_list(qtbot, page.category_filter)

    assert view.verticalScrollBar().maximum() > 0
    assert_spaced(view)
