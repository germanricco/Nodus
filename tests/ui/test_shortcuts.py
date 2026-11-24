"""Every shortcut of the table does what Ayuda says, and tells its keys where it shows
(ui/shortcuts.py; the window binds them in shell/main_window.py)."""

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from nodus.ui.navigation import DetailId, PageId
from nodus.ui.shell.history import NavigationHistory, Place
from nodus.ui.shortcuts import SHORTCUTS, page_keys

CTRL, ALT = Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.AltModifier


def press(window, key: Qt.Key, modifier=CTRL) -> None:
    QTest.keyClick(window, key, modifier)
    QApplication.processEvents()


def test_ctrl_and_a_number_opens_that_page_of_the_sidebar(window):
    press(window, Qt.Key.Key_5)
    assert window.current_page_id is PageId.BUDGETS
    press(window, Qt.Key.Key_9)
    assert window.current_page_id is PageId.PAYEES
    assert list(page_keys()) == [p for p in PageId if p is not PageId.SETTINGS][:9]


def test_alt_arrows_go_back_and_forward_through_the_pages_visited(window):
    window.show_page(PageId.ACCOUNTS)
    window.show_page(PageId.GOALS)

    press(window, Qt.Key.Key_Left, ALT)
    assert window.current_page_id is PageId.ACCOUNTS
    press(window, Qt.Key.Key_Left, ALT)
    assert window.current_page_id is PageId.DASHBOARD
    press(window, Qt.Key.Key_Left, ALT)  # nothing before the first page
    assert window.current_page_id is PageId.DASHBOARD
    press(window, Qt.Key.Key_Right, ALT)
    assert window.current_page_id is PageId.ACCOUNTS


def test_ctrl_f_searches_the_page_or_else_transacciones(window):
    window.show_page(PageId.PAYEES)
    press(window, Qt.Key.Key_F)
    assert window.page(PageId.PAYEES).search_input.hasFocus()

    window.show_page(PageId.BUDGETS)
    press(window, Qt.Key.Key_F)
    assert window.current_page_id is PageId.TRANSACTIONS
    search = window.page(PageId.TRANSACTIONS).search_input
    assert search.hasFocus()
    assert "(Ctrl+F)" in search.toolTip()


def test_ctrl_h_hides_the_amounts(window, services):
    press(window, Qt.Key.Key_H)
    assert services.settings.amounts_hidden()
    press(window, Qt.Key.Key_H)
    assert not services.settings.amounts_hidden()


def test_ctrl_n_asks_for_an_account_before_a_transaction(window, monkeypatch):
    told = []
    monkeypatch.setattr("nodus.ui.shell.main_window.tell", lambda *args: told.append(args))

    press(window, Qt.Key.Key_N)

    assert told and window.current_page_id is PageId.ACCOUNTS


def test_the_buttons_with_a_shortcut_tell_it(window):
    assert window.top_bar._add_button.toolTip() == "Agregar transacción (Ctrl+N)"
    assert window.top_bar.help_button.toolTip() == "Ayuda (F1)"
    assert window.sidebar.nav_button(PageId.DASHBOARD).toolTip() == "Inicio (Ctrl+1)"


def test_every_shortcut_is_in_the_table_once():
    assert len({(s.keys, s.group) for s in SHORTCUTS}) == len(SHORTCUTS)


class TestHistory:
    def test_a_new_visit_forgets_what_was_ahead(self):
        history = NavigationHistory()
        for page in (PageId.DASHBOARD, PageId.ACCOUNTS, PageId.GOALS):
            history.visit(Place(page))
        history.back()
        history.visit(Place(PageId.TAGS))

        assert history.forward() is None
        assert history.back() == Place(PageId.ACCOUNTS)

    def test_a_page_that_leads_elsewhere_while_going_back_takes_its_place(self):
        history = NavigationHistory()
        history.visit(Place(PageId.ACCOUNTS))
        history.visit(Place(DetailId.ACCOUNT, 7))
        history.visit(Place(PageId.GOALS))
        history.back()
        with history.moving():  # the account was deleted: its page goes to the list
            history.visit(Place(PageId.ACCOUNTS))

        assert history.current == Place(PageId.ACCOUNTS)
        assert history.forward() == Place(PageId.GOALS)

    def test_keeps_the_last_fifty(self):
        history = NavigationHistory()
        for number in range(80):
            history.visit(Place(DetailId.TAG, number))
        steps = 0
        while history.back() is not None:
            steps += 1

        assert steps == NavigationHistory.LIMIT
