from factories import ars, expense_draft
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.ui.main_window import MainWindow
from nodus.ui.navigation import PageId
from nodus.ui.widgets.sidebar import Sidebar


def sidebar_texts(window) -> list[str]:
    return [label.text() for label in window.sidebar.findChildren(QLabel) if label.isVisible()]


def test_opens_on_dashboard(window):
    assert window.isVisible()
    assert window.windowTitle() == "Nodus"
    assert window.current_page is window.page(PageId.DASHBOARD)


def test_sidebar_buttons_navigate(window, qtbot):
    for page_id in PageId:
        button = window.sidebar.nav_button(page_id)
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

        assert window.current_page is window.page(page_id)
        assert button.isChecked()


def test_edit_in_a_transactions_filter_opens_its_page(window):
    window.show_page(PageId.TRANSACTIONS)
    combo = window.page(PageId.TRANSACTIONS).category_filter

    combo.view().pressed.emit(combo.model().index(combo.count() - 1, 0))

    assert window.current_page is window.page(PageId.CATEGORIES)
    assert window.sidebar.nav_button(PageId.CATEGORIES).isChecked()


def test_sidebar_shows_empty_state_without_accounts(window):
    assert "Todavía no hay cuentas" in sidebar_texts(window)


def test_sidebar_lists_accounts_with_balances(window, qtbot, pesos, dollars):
    window.sidebar.refresh_accounts()

    # Qt shows widgets added to a visible parent on the next event loop pass.
    qtbot.waitUntil(lambda: "Banco" in sidebar_texts(window))
    texts = sidebar_texts(window)
    assert "$ 100.000,00" in texts
    assert "US$ 500,00" in texts
    assert "Todavía no hay cuentas" not in texts


def test_sidebar_refreshes_when_data_changes(window, services, event_bus, qtbot, pesos):
    window.sidebar.refresh_accounts()
    services.transactions.create(expense_draft(services, pesos.id, ars("2500")))
    services.accounts.create("Efectivo", AccountType.CASH, Currency.ARS, ars("0"))

    event_bus.transactions_changed.emit()

    qtbot.waitUntil(lambda: "$ 97.500,00" in sidebar_texts(window))
    assert "Efectivo" in sidebar_texts(window)


def test_sidebar_collapses_to_icons_and_remembers_it(
    window, qtbot, services, event_bus, theme_manager, pesos
):
    window.sidebar.refresh_accounts()
    button = window.sidebar.nav_button(PageId.BUDGETS)

    window.sidebar.collapse_button.click()

    assert window.sidebar.width() == Sidebar.COLLAPSED_WIDTH
    assert button.text() == ""
    assert button.toolTip() == PageId.BUDGETS.label
    assert "Banco" not in sidebar_texts(window)
    reopened = MainWindow(services, event_bus, theme_manager)
    qtbot.addWidget(reopened)
    assert reopened.sidebar.is_collapsed

    window.sidebar.collapse_button.click()

    assert button.text() == PageId.BUDGETS.label
    assert not services.settings.sidebar_collapsed()


def test_eye_hides_balances_and_net_worth_and_remembers_it(
    window, qtbot, services, event_bus, theme_manager, pesos
):
    window.sidebar.refresh_accounts()
    window.show_page(PageId.ACCOUNTS)
    accounts = window.page(PageId.ACCOUNTS)

    window.top_bar.hide_amounts_button.click()

    qtbot.waitUntil(lambda: "$ ••••" in sidebar_texts(window))
    assert "$ 100.000,00" not in sidebar_texts(window)
    balances = [label.text() for label in accounts.findChildren(QLabel) if label.isVisible()]
    assert "$ 100.000,00" not in balances
    assert accounts.net_worth_card.total_label.text() == "$ ••••"
    window.show_page(PageId.DASHBOARD)
    assert window.page(PageId.DASHBOARD).net_worth_card.total_label.text() == "$ ••••"
    assert window.top_bar.hide_amounts_button.toolTip() == "Mostrar montos"
    reopened = MainWindow(services, event_bus, theme_manager)
    qtbot.addWidget(reopened)
    assert reopened.top_bar.hide_amounts_button.toolTip() == "Mostrar montos"

    window.top_bar.hide_amounts_button.click()

    qtbot.waitUntil(lambda: "$ 100.000,00" in sidebar_texts(window))
    assert not services.settings.amounts_hidden()


def test_accounts_fold_under_their_title(window, qtbot, services, pesos):
    window.sidebar.refresh_accounts()
    qtbot.waitUntil(lambda: "Banco" in sidebar_texts(window))

    window.sidebar.toggle_accounts_folded()

    assert "Banco" not in sidebar_texts(window)
    assert services.settings.accounts_folded()
    window.sidebar.toggle_accounts_folded()
    assert "Banco" in sidebar_texts(window)
