"""Pages about one item: how to get there and back, what they show, and deleting."""

from factories import ars, expense_draft, usd
from menus import run_action
from PySide6.QtCore import Qt

from nodus.models.transaction_filter import TransactionFilter
from nodus.ui.navigation import DetailId, PageId
from nodus.ui.pages import accounts_page, payees_page
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

    def test_a_foreign_account_shows_its_value_in_pesos(self, window, pesos, dollars):
        window.show_detail(DetailId.ACCOUNT, dollars.id)
        detail = window.detail(DetailId.ACCOUNT)

        assert not detail.converted_tile.isHidden()
        assert not detail.gain_tile.isHidden()  # savings change value
        assert not detail.value_button.isHidden()
        window.show_detail(DetailId.ACCOUNT, pesos.id)
        assert detail.converted_tile.isHidden()
        assert detail.gain_tile.isHidden()

    def test_the_back_arrow_names_where_it_goes(self, window, pesos):
        window.show_detail(DetailId.ACCOUNT, pesos.id)

        assert window.detail(DetailId.ACCOUNT).back_button.toolTip() == "Volver a Cuentas (Esc)"

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


class TestPayeeDetail:
    def test_a_double_click_opens_it_with_its_figures(self, qtbot, services, window, pesos):
        for amount in ("100", "50"):
            services.transactions.create(
                expense_draft(services, pesos.id, ars(amount), payee_name="Coto")
            )
        services.transactions.create(expense_draft(services, pesos.id, ars("7")))
        window.show_page(PageId.PAYEES)
        payees = window.page(PageId.PAYEES)

        payees.table.row_activated.emit(0)

        detail = window.detail(DetailId.PAYEE)
        assert window.current_page is detail
        assert detail.title_label.text() == "Coto"
        figures = {caption: label.text() for caption, label in detail.figure_labels.items()}
        assert figures["Movimientos"] == "2"
        assert figures["Total"] == "-$ 150,00"
        assert figures["Categoría habitual"] != "—"
        assert detail.list_view.model.rowCount() == 2
        assert not detail.merge_button.isEnabled()  # no other payee to merge with
        qtbot.keyClick(detail, Qt.Key.Key_Escape)
        assert window.current_page is payees

    def test_the_danger_zone_keeps_the_movements(self, monkeypatch, services, window, pesos):
        services.transactions.create(
            expense_draft(services, pesos.id, ars("100"), payee_name="Coto")
        )
        coto = services.payees.find("Coto")
        answers = []
        monkeypatch.setattr(
            payees_page, "confirm", lambda _parent, _title, text: answers.append(text) or True
        )
        window.show_detail(DetailId.PAYEE, coto.id)
        detail = window.detail(DetailId.PAYEE)
        assert "1 movimiento queda sin beneficiario" in detail.delete_warning(detail.summary)

        detail.delete_button.click()

        assert answers
        assert services.payees.find("Coto") is None
        assert len(services.transactions.list_transactions(TransactionFilter())) == 1
        assert window.current_page is window.page(PageId.PAYEES)


class TestTagDetail:
    def test_the_menu_opens_it_and_a_merge_goes_back(self, services, event_bus, window, pesos):
        services.transactions.create(
            expense_draft(services, pesos.id, ars("100"), tag_names=("Viaje", "Vacaciones"))
        )
        viaje, vacaciones = services.tags.find("Viaje"), services.tags.find("Vacaciones")
        window.show_page(PageId.TAGS)
        tags = window.page(PageId.TAGS)
        row = [tags.summary_at(r).tag.id for r in range(tags.proxy.rowCount())].index(viaje.id)

        run_action(tags.row_actions(row), "Abrir")

        detail = window.detail(DetailId.TAG)
        assert window.current_page is detail
        assert detail.title_label.text() == "Viaje"
        assert detail.merge_button.isEnabled()
        services.tags.merge_many([viaje.id], vacaciones.id)
        event_bus.tags_changed.emit()
        assert window.current_page is tags
