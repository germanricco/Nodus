"""Every row with actions answers the keyboard the same way (widgets/tables/row_actions.py):
↑ and ↓ move between rows, Enter runs the main action, the Menu key or Mayús+F10 opens
the menu, ← and → fold a group, and Alt+↑ and Alt+↓ move an account in its group."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from nodus.models.transaction import TransactionType
from nodus.ui.navigation import DetailId, PageId
from nodus.ui.pages.accounts_page import AccountRow
from nodus.ui.pages.categories_page import CategoryRow
from nodus.ui.widgets.tables import row_actions
from nodus.ui.widgets.tables.row_actions import focus_row

ALT, SHIFT = Qt.KeyboardModifier.AltModifier, Qt.KeyboardModifier.ShiftModifier


def settle() -> None:
    for _ in range(5):
        QApplication.processEvents()


def press(key: Qt.Key, modifier=Qt.KeyboardModifier.NoModifier) -> None:
    QTest.keyClick(QApplication.focusWidget(), key, modifier)
    settle()


def shown(window, kind) -> list[QWidget]:
    rows = [row for row in window.findChildren(kind) if row.isVisible()]
    return sorted(rows, key=lambda row: row.mapToGlobal(row.rect().topLeft()).y())


@pytest.fixture
def accounts(window, pesos, dollars):
    window.show_page(PageId.ACCOUNTS)
    window.activateWindow()
    settle()
    rows = shown(window, AccountRow)
    focus_row(rows[0])
    settle()
    return rows


def name_of(row: QWidget) -> str:
    return row_actions.row_identity(row)


def test_tab_reaches_a_row_but_a_click_leaves_no_ring(accounts):
    assert accounts[0].focusPolicy() == Qt.FocusPolicy.TabFocus
    assert accounts[0].hasFocus()
    assert accounts[0].accessibleName().startswith(name_of(accounts[0]))


def test_arrows_move_between_rows(window, accounts):
    press(Qt.Key.Key_Down)
    assert QApplication.focusWidget() is accounts[1]
    press(Qt.Key.Key_Up)
    press(Qt.Key.Key_Up)  # nothing above the first
    assert QApplication.focusWidget() is accounts[0]


def test_enter_runs_the_main_action(window, accounts):
    press(Qt.Key.Key_Return)
    assert window.current_page is window.detail(DetailId.ACCOUNT)


def test_the_menu_key_and_shift_f10_open_the_menu(window, accounts, monkeypatch):
    opened = []
    monkeypatch.setattr(row_actions, "show_menu", lambda *args: opened.append(args) or FakeMenu())

    press(Qt.Key.Key_Menu)
    press(Qt.Key.Key_F10, SHIFT)

    assert len(opened) == 2


class FakeMenu:
    class _Signal:
        def connect(self, _slot) -> None:
            pass

    aboutToHide = _Signal()  # noqa: N815


def test_alt_arrows_move_an_account_and_keep_the_keyboard_on_it(window, accounts, services):
    moved = name_of(accounts[0])

    press(Qt.Key.Key_Down, ALT)
    QTest.qWait(50)

    rows = shown(window, AccountRow)
    assert [name_of(row) for row in rows].index(moved) == 1
    assert QApplication.focusWidget() is rows[1]


def test_left_and_right_fold_a_category_with_subcategories(window, services):
    expense = TransactionType.EXPENSE
    food = services.categories.create("Comida", expense, "#000000")
    services.categories.create("Supermercado", expense, "#000000", parent_id=food.id)
    window.show_page(PageId.CATEGORIES)
    window.activateWindow()
    settle()
    row = next(r for r in shown(window, CategoryRow) if r.category.id == food.id)
    focus_row(row)
    settle()

    press(Qt.Key.Key_Left)
    QTest.qWait(50)

    assert services.settings.folded_categories() == {food.id}
    focused = QApplication.focusWidget()
    assert isinstance(focused, CategoryRow) and focused.category.id == food.id
    press(Qt.Key.Key_Right)
    QTest.qWait(50)
    assert services.settings.folded_categories() == set()
