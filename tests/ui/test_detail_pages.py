"""Pages about one item: how to get there and back, what they show, and deleting."""

from datetime import date

import pytest
from factories import (
    TODAY,
    ars,
    category_id,
    charge_draft,
    expense_draft,
    income_draft,
    light_theme,
    usd,
)
from menus import double_click_row, run_action, texts
from PySide6.QtCore import Qt

from nodus.models.transaction import TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.ui.dialogs import confirm as confirm_dialog
from nodus.ui.dialogs.transaction_dialog import INCOME_MODE, TransactionDialog, TransactionStart
from nodus.ui.navigation import DetailId, PageId, RecordLink
from nodus.ui.pages.accounts_page import AccountRow
from nodus.ui.pages.categories_page import CategoryRow
from nodus.ui.widgets.tables.transaction_table import CATEGORY

EXPENSE, INCOME = TransactionType.EXPENSE, TransactionType.INCOME


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

        window.sidebar.record_requested.emit(RecordLink.account(pesos.id))
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

    def test_says_what_it_is_and_where_it_sits(self, services, window, pesos):
        bancos = services.account_groups.create("Bancos")
        services.account_groups.move_account(pesos.id, bancos.id)

        window.show_detail(DetailId.ACCOUNT, pesos.id)

        assert window.detail(DetailId.ACCOUNT).context_label.text() == (
            "Cuenta bancaria · ARS · Bancos"
        )

    def test_this_months_money_in_and_out(self, services, window, pesos):
        services.transactions.create(income_draft(services, pesos.id, ars("5000")))
        services.transactions.create(expense_draft(services, pesos.id, ars("300")))
        window.show_detail(DetailId.ACCOUNT, pesos.id)
        detail = window.detail(DetailId.ACCOUNT)
        detail.today = TODAY
        detail.refresh()

        assert detail.incoming_label.text() == "$ 5.000,00"
        assert detail.outgoing_label.text() == "$ 300,00"
        assert detail.balance_note.text() == "+$ 4.700,00 este mes"

    def test_its_payments_show_with_their_pay_button(self, services, window, pesos, dollars):
        services.recurring.create(charge_draft(services, pesos.id, ars("9000")))
        window.show_detail(DetailId.ACCOUNT, pesos.id)
        detail = window.detail(DetailId.ACCOUNT)

        assert not detail.payments_card.isHidden()
        assert [row.charge.name for row in detail.payment_rows] == ["Internet"]
        window.show_detail(DetailId.ACCOUNT, dollars.id)
        assert detail.payments_card.isHidden()

    def test_the_chart_range_is_remembered(self, services, window, pesos):
        window.show_detail(DetailId.ACCOUNT, pesos.id)
        detail = window.detail(DetailId.ACCOUNT)

        detail.range_input.buttons[0].click()

        assert services.settings.account_chart_months() == 6

    def test_the_back_arrow_names_where_it_goes(self, window, pesos):
        window.show_detail(DetailId.ACCOUNT, pesos.id)

        assert window.detail(DetailId.ACCOUNT).back_button.toolTip() == "Volver a Cuentas (Esc)"

    def test_deleting_is_in_the_header_menu_and_asks_first(
        self, monkeypatch, services, window, pesos, dollars
    ):
        answers = []
        monkeypatch.setattr(
            confirm_dialog, "confirm", lambda _parent, _title, text: answers.append(text) or True
        )
        window.show_detail(DetailId.ACCOUNT, pesos.id)

        actions = window.detail(DetailId.ACCOUNT).more_actions()
        assert actions[-1].text == "Eliminar" and actions[-1].destructive
        run_action(actions, "Eliminar")

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

        double_click_row(payees.table, 0)

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

    def test_deleting_from_the_menu_keeps_the_movements(self, monkeypatch, services, window, pesos):
        services.transactions.create(
            expense_draft(services, pesos.id, ars("100"), payee_name="Coto")
        )
        coto = services.payees.find("Coto")
        answers = []
        monkeypatch.setattr(
            confirm_dialog, "confirm", lambda _parent, _title, text: answers.append(text) or True
        )
        window.show_detail(DetailId.PAYEE, coto.id)
        detail = window.detail(DetailId.PAYEE)

        run_action(detail.more_actions(), "Eliminar")

        assert "1 movimiento queda sin beneficiario" in answers[0]
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


class TestCategoryDetail:
    @pytest.fixture
    def vivienda(self, services, window, pesos):
        """«Vivienda» with «Alquiler» inside, a movement in each, the page set on TODAY."""
        vivienda = category_id(services, "Vivienda", EXPENSE)
        alquiler = services.categories.create("Alquiler", EXPENSE, "#000000", vivienda)
        for amount, category in (("400", alquiler.id), ("100", vivienda)):
            services.transactions.create(
                expense_draft(services, pesos.id, ars(amount), category_id=category)
            )
        window.detail(DetailId.CATEGORY).today = TODAY
        return services.categories.get(vivienda)

    def open(self, window, category_id):
        window.show_detail(DetailId.CATEGORY, category_id)
        return window.detail(DetailId.CATEGORY)

    def test_a_click_in_categorias_opens_it(self, window, vivienda):
        window.show_page(PageId.CATEGORIES)
        categories = window.page(PageId.CATEGORIES)
        row = next(r for r in categories.findChildren(CategoryRow) if r.category == vivienda)

        run_action(row.actions(), "Abrir")

        detail = window.detail(DetailId.CATEGORY)
        assert window.current_page is detail
        assert detail.title_label.text() == "Vivienda"

    def test_its_figures_months_and_subcategories(self, window, vivienda):
        detail = self.open(window, vivienda.id)

        figures = {caption: label.text() for caption, label in detail.figure_labels.items()}
        assert figures["Total"] == "$ 500,00"
        assert figures["Este mes"] == "$ 500,00"
        assert figures["Movimientos"] == "2"
        assert len(detail.chart.bars()) == 12
        assert [link.text() for link in detail.related_line.links] == ["Alquiler"]
        # Its movements may be in a subcategory, so the list says which.
        assert not detail.list_view.table.isColumnHidden(CATEGORY)
        assert detail.list_view.model.rowCount() == 2

    def test_a_subcategory_links_to_its_parent(self, services, window, vivienda):
        alquiler = next(c for c in services.categories.list_categories(EXPENSE)
                        if c.name == "Alquiler")  # fmt: skip
        detail = self.open(window, alquiler.id)

        assert detail.list_view.table.isColumnHidden(CATEGORY)
        detail.related_line.links[0].click()

        assert detail.title_label.text() == "Vivienda"
        # With subcategories, merging would take them along: first they go.
        assert not detail.merge_button.isEnabled()

    def test_otros_is_only_shown(self, services, window):
        otros = next(c for c in services.categories.list_categories(EXPENSE) if c.is_system)

        detail = self.open(window, otros.id)

        assert not detail.edit_button.isVisibleTo(detail)
        assert not detail.merge_button.isVisibleTo(detail)
        assert detail.more_actions() == []

    def test_deleting_from_the_menu_goes_back(self, monkeypatch, services, window, vivienda):
        monkeypatch.setattr(confirm_dialog, "confirm", lambda *_args: True)
        detail = self.open(window, vivienda.id)
        assert texts(detail.more_actions()) == ["Agregar subcategoría", "Eliminar"]

        run_action(detail.more_actions(), "Eliminar")

        assert "Vivienda" not in [c.name for c in services.categories.list_categories(EXPENSE)]
        assert window.current_page is window.page(PageId.CATEGORIES)

    def test_a_new_movement_starts_in_the_category(self, qtbot, services, event_bus, window):
        sueldo = category_id(services, "Sueldo", INCOME)
        start = TransactionStart(category_id=sueldo)

        dialog = TransactionDialog(services, event_bus, light_theme(), start=start)
        qtbot.addWidget(dialog)

        assert dialog.mode_input.index() == INCOME_MODE
        assert dialog.category_input.current_id() == sueldo

    def test_this_month_against_the_one_before(self, services, window, pesos):
        ocio = category_id(services, "Ocio", EXPENSE)
        for amount, day in (("100", date(2026, 10, 3)), ("150", TODAY)):
            services.transactions.create(
                expense_draft(services, pesos.id, ars(amount), day, category_id=ocio)
            )
        window.detail(DetailId.CATEGORY).today = TODAY

        badge = self.open(window, ocio).change_badge

        assert badge.text() == "↗ 50 %"
        assert badge.property("tone") == "bad"  # more spending
        assert badge.toolTip() == "Mes anterior: $ 100,00"

    def test_new_this_month_or_nothing_to_compare(self, services, window, vivienda):
        assert self.open(window, vivienda.id).change_badge.text() == "Nueva"

        ropa = category_id(services, "Ropa", EXPENSE)
        assert not self.open(window, ropa).change_badge.isVisibleTo(window)
