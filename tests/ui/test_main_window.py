from factories import ars, expense_draft
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.ui.navigation import PageId


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
