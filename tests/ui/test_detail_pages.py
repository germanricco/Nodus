"""Pages about one item: how to get there and back, what they show, and deleting."""

from factories import ars, expense_draft, usd
from PySide6.QtCore import Qt

from nodus.ui.navigation import DetailId, PageId
from nodus.ui.pages import accounts_page
from nodus.ui.pages.accounts_page import AccountRow


def account_row(window, account_id: int) -> AccountRow:
    window.show_page(PageId.ACCOUNTS)
    rows = window.page(PageId.ACCOUNTS).findChildren(AccountRow)
    return next(row for row in rows if row.account.id == account_id)


class TestAccountDetail:
    def test_a_click_on_the_row_opens_it_and_esc_goes_back(self, qtbot, window, pesos):
        row = account_row(window, pesos.id)

        qtbot.mouseClick(row, Qt.MouseButton.LeftButton)

        detail = window.detail(DetailId.ACCOUNT)
        assert window.current_page is detail
        assert detail.title_label.text() == "Banco"
        assert window.sidebar.nav_button(PageId.ACCOUNTS).isChecked()
        qtbot.keyClick(detail, Qt.Key.Key_Escape)
        assert window.current_page is window.page(PageId.ACCOUNTS)

    def test_the_sidebar_opens_it_and_the_back_link_returns(self, window, pesos):
        window.sidebar.refresh_accounts()
        window.show_page(PageId.DASHBOARD)

        window.sidebar.account_requested.emit(pesos.id)
        detail = window.detail(DetailId.ACCOUNT)
        assert window.current_page is detail
        detail.back_button.click()

        assert window.current_page is window.page(PageId.ACCOUNTS)

    def test_shows_only_its_movements_and_follows_changes(
        self, services, event_bus, window, pesos, dollars
    ):
        services.transactions.create(expense_draft(services, dollars.id, usd("1")))
        window.show_detail(DetailId.ACCOUNT, pesos.id)
        detail = window.detail(DetailId.ACCOUNT)
        assert detail.list_view.model.rowCount() == 0
        assert not detail.list_view.empty_state.isHidden()

        services.transactions.create(expense_draft(services, pesos.id, ars("10")))
        event_bus.transactions_changed.emit()

        assert detail.list_view.model.rowCount() == 1
        assert detail.balance_label.text() == "$ 99.990,00"
        assert detail.value_button.isHidden()  # a bank account does not change value

    def test_a_foreign_account_shows_its_value_in_pesos(self, window, dollars):
        window.show_detail(DetailId.ACCOUNT, dollars.id)
        detail = window.detail(DetailId.ACCOUNT)

        assert not detail.converted_label.isHidden()
        assert not detail.value_button.isHidden()  # savings change value

    def test_the_danger_zone_asks_before_deleting(
        self, monkeypatch, services, window, pesos, dollars
    ):
        answers = []
        monkeypatch.setattr(
            accounts_page, "confirm", lambda _parent, _title, text: answers.append(text) or True
        )
        window.show_detail(DetailId.ACCOUNT, pesos.id)

        window.detail(DetailId.ACCOUNT).delete_button.click()

        assert answers and "«Banco»" in answers[0]
        assert [a.id for a in services.accounts.list_accounts()] == [dollars.id]
        assert window.current_page is window.page(PageId.ACCOUNTS)
