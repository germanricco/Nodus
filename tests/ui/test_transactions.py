from datetime import date

import pytest
from factories import ars, category_id, expense_draft, income_draft, light_theme, usd
from menus import run_action, texts
from PySide6.QtCore import Qt

from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.transaction_service import TransferDraft
from nodus.ui import main_window as main_window_module
from nodus.ui.dialogs import export
from nodus.ui.dialogs.change_category_dialog import ChangeCategoryDialog
from nodus.ui.dialogs.transaction_dialog import (
    EXPENSE_MODE,
    INCOME_MODE,
    TRANSFER_MODE,
    TransactionDialog,
)
from nodus.ui.navigation import PageId
from nodus.ui.pages import transactions_page
from nodus.ui.pages.transactions_page import TransactionsPage
from nodus.ui.widgets.selectors import HEADING_ROLE, MANAGE_ROLE
from nodus.ui.widgets.transaction_table import AMOUNT, CATEGORY, PAYEE

EXPENSE = TransactionType.EXPENSE
NOVEMBER = Month(2026, 11)


def make_dialog(qtbot, services, event_bus, transaction=None) -> TransactionDialog:
    dialog = TransactionDialog(services, event_bus, light_theme(), transaction)
    qtbot.addWidget(dialog)
    return dialog


def save(qtbot, dialog) -> None:
    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)


def all_transactions(services):
    return services.transactions.list_transactions(TransactionFilter())


def buy_dollars(services, pesos, dollars):
    return services.transactions.create_transfer(
        TransferDraft(pesos.id, dollars.id, ars("121550"), date(2026, 11, 4), amount_in=usd("100"))
    )


class TestTransactionDialog:
    def test_new_dialog_offers_the_last_account_used(
        self, qtbot, services, event_bus, pesos, dollars
    ):
        first = make_dialog(qtbot, services, event_bus)
        assert first.account_input.current_id() == pesos.id  # the first in the user's order
        first.account_input.select(dollars.id)
        first.amount_input.line_edit.setText("100")
        save(qtbot, first)

        assert make_dialog(qtbot, services, event_bus).account_input.current_id() == dollars.id

    def test_archived_last_account_is_not_offered(self, qtbot, services, event_bus, pesos, dollars):
        services.settings.set_last_account_id(pesos.id)
        services.accounts.set_archived(pesos.id, True)

        assert make_dialog(qtbot, services, event_bus).account_input.current_id() == dollars.id

    def test_records_expense_in_chosen_category(self, qtbot, services, event_bus, pesos):
        dialog = make_dialog(qtbot, services, event_bus)
        dialog.amount_input.line_edit.setText("1.500,50")
        dialog.category_input.select(category_id(services, "Ocio", EXPENSE))
        dialog.note_input.setText("Cine")

        with qtbot.waitSignal(event_bus.transactions_changed):
            save(qtbot, dialog)

        [saved] = all_transactions(services)
        assert saved.type is EXPENSE
        assert saved.amount == ars("1500.50")
        assert saved.category_id == category_id(services, "Ocio", EXPENSE)
        assert saved.note == "Cine"
        assert saved.occurred_on == date.today()

    def test_dialog_shrinks_and_grows_with_its_fields(
        self, qtbot, services, event_bus, pesos, dollars
    ):
        dialog = make_dialog(qtbot, services, event_bus)
        dialog.show()
        qtbot.waitExposed(dialog)
        expense_height = dialog.height()

        # The layout applies a new size on the next pass of the event loop.
        dialog.mode_input.set_index(TRANSFER_MODE)
        qtbot.waitUntil(lambda: dialog.height() < expense_height)  # no payee, category, tags
        dialog.mode_input.set_index(EXPENSE_MODE)
        qtbot.waitUntil(lambda: dialog.height() == expense_height)

        assert dialog.width() == 460

    def test_fields_stay_in_place_across_modes(self, qtbot, services, event_bus, pesos, dollars):
        dialog = make_dialog(qtbot, services, event_bus)
        dialog.show()
        qtbot.waitExposed(dialog)
        positions = set()

        for mode in (EXPENSE_MODE, INCOME_MODE, TRANSFER_MODE):
            dialog.mode_input.set_index(mode)
            dialog.layout().activate()
            positions.add(dialog.amount_input.geometry().x())

        assert len(positions) == 1

    def test_category_choices_follow_mode(self, qtbot, services, event_bus, pesos):
        dialog = make_dialog(qtbot, services, event_bus)

        dialog.mode_input.set_index(INCOME_MODE)

        names = [
            dialog.category_input.itemText(i).strip() for i in range(dialog.category_input.count())
        ]
        assert names == ["Reembolsos", "Sueldo", "Trabajo freelance", "Otros"]

    def test_transfer_between_currencies_shows_implied_rate(
        self, qtbot, services, event_bus, pesos, dollars
    ):
        dialog = make_dialog(qtbot, services, event_bus)
        dialog.mode_input.set_index(TRANSFER_MODE)
        dialog.account_input.select(pesos.id)
        dialog.to_account_input.select(dollars.id)
        dialog.amount_input.line_edit.setText("121.550")
        assert not dialog.rate_hint.isVisibleTo(dialog)
        dialog.amount_in_input.line_edit.setText("100")

        assert dialog.amount_in_input.isVisibleTo(dialog)
        assert dialog.rate_hint.isVisibleTo(dialog)
        assert not dialog.category_input.isVisibleTo(dialog)
        assert dialog.rate_hint.text() == "Cotización implícita: US$ 1 = $ 1.215,50"

        save(qtbot, dialog)

        [outgoing] = services.transactions.list_transactions(TransactionFilter(account_id=pesos.id))
        transfer = services.transactions.get_transfer(outgoing.transfer_id)
        assert transfer.incoming.amount == usd("100")

    def test_new_transfer_starts_with_a_different_destination(
        self, qtbot, services, event_bus, pesos, dollars
    ):
        dialog = make_dialog(qtbot, services, event_bus)

        dialog.mode_input.set_index(TRANSFER_MODE)

        assert dialog.account_input.current_id() != dialog.to_account_input.current_id()

    def test_same_currency_transfer_hides_incoming_amount(self, qtbot, services, event_bus, pesos):
        services.accounts.create("Efectivo", pesos.type, pesos.currency, ars("0"))
        dialog = make_dialog(qtbot, services, event_bus)

        dialog.mode_input.set_index(TRANSFER_MODE)

        assert not dialog.amount_in_input.isVisibleTo(dialog)

    def test_editing_transfer_locks_mode_and_updates_both_legs(
        self, qtbot, services, event_bus, pesos, dollars
    ):
        transfer = buy_dollars(services, pesos, dollars)
        dialog = make_dialog(qtbot, services, event_bus, transfer.incoming)

        assert dialog.mode_input.index() == TRANSFER_MODE
        assert not dialog.mode_input.buttons[EXPENSE_MODE].isEnabled()
        assert dialog.account_input.current_id() == pesos.id
        assert dialog.amount_in_input.money() == usd("100")

        dialog.amount_in_input.line_edit.setText("101")
        save(qtbot, dialog)

        assert services.transactions.get_transfer(transfer.id).incoming.amount == usd("101")
        assert len(all_transactions(services)) == 2

    def test_editing_expense_keeps_category_and_can_become_income(
        self, qtbot, services, event_bus, pesos
    ):
        expense = services.transactions.create(expense_draft(services, pesos.id, ars("10")))
        dialog = make_dialog(qtbot, services, event_bus, expense)

        assert dialog.category_input.current_id() == expense.category_id
        assert not dialog.mode_input.buttons[TRANSFER_MODE].isEnabled()

        dialog.mode_input.set_index(INCOME_MODE)
        save(qtbot, dialog)

        assert services.transactions.get(expense.id).type is TransactionType.INCOME

    def test_invalid_amount_keeps_dialog_open_with_error(self, qtbot, services, event_bus, pesos):
        dialog = make_dialog(qtbot, services, event_bus)
        dialog.amount_input.line_edit.setText("0")

        save(qtbot, dialog)

        assert dialog.error_label.text() == "El monto debe ser mayor que cero."
        assert all_transactions(services) == []


@pytest.fixture
def page(qtbot, services, event_bus, theme_manager) -> TransactionsPage:
    transactions = TransactionsPage(services, event_bus, theme_manager)
    qtbot.addWidget(transactions)
    transactions.period_selector.set_period(Period.of_months(NOVEMBER))
    transactions.refresh()
    return transactions


def column(page, index: int) -> list[str]:
    model = page.model
    return [model.data(model.index(row, index)) for row in range(model.rowCount())]


def populate(services, pesos, dollars) -> None:
    services.transactions.create(
        expense_draft(services, pesos.id, ars("2500"), occurred_on=date(2026, 11, 2), note="Pizza")
    )
    services.transactions.create(
        income_draft(services, pesos.id, ars("900000"), occurred_on=date(2026, 11, 1))
    )
    services.transactions.create(
        expense_draft(services, pesos.id, ars("99"), occurred_on=date(2026, 10, 31), note="Viejo")
    )
    buy_dollars(services, pesos, dollars)


class TestTransactionsPage:
    def test_lists_month_newest_first_with_transfer_as_one_row(
        self, services, page, pesos, dollars
    ):
        populate(services, pesos, dollars)

        page.refresh()

        assert column(page, AMOUNT) == ["$ 121.550,00 → US$ 100,00", "-$ 2.500,00", "$ 900.000,00"]
        assert column(page, CATEGORY)[0] == "Transferencia"
        assert page.model.item(0).account_text == "Banco → Ahorro"

    def test_filters_by_type_text_and_month(self, services, page, pesos, dollars):
        populate(services, pesos, dollars)
        page.refresh()

        page.type_filter.setCurrentText("Gastos")
        assert column(page, AMOUNT) == ["-$ 2.500,00"]

        page.type_filter.setCurrentText("Tipo")
        page.search_input.setText("viejo")
        assert column(page, AMOUNT) == []
        assert page.empty_label.isVisibleTo(page)

        page.period_selector.set_period(Period.of_months(NOVEMBER.previous()))
        assert column(page, AMOUNT) == ["-$ 99,00"]

    def test_clear_filters_keeps_month_and_shows_everything(self, services, page, pesos, dollars):
        populate(services, pesos, dollars)
        page.refresh()
        assert not page.clear_filters_button.isEnabled()
        page.account_filter.select(dollars.id)
        page.type_filter.setCurrentText("Transferencias")
        page.search_input.setText("nada")
        assert page.clear_filters_button.isEnabled()

        page.clear_filters_button.click()

        assert page.current_filter() == TransactionFilter(start=NOVEMBER.start, end=NOVEMBER.end)
        assert len(column(page, AMOUNT)) == 3
        assert not page.clear_filters_button.isEnabled()

    def test_unused_filters_show_their_name_and_active_ones_stand_out(self, page, pesos):
        page.refresh()
        assert page.category_filter.currentText() == "Categoría"
        assert page.category_filter.property("filter") == "idle"

        page.account_filter.select(pesos.id)

        assert page.account_filter.property("filter") == "active"
        assert page.type_filter.property("filter") == "idle"
        page.clear_filters_button.click()
        assert page.account_filter.property("filter") == "idle"

    def test_category_filter_splits_sections_with_unselectable_headings(self, page):
        page.refresh()
        combo = page.category_filter
        headings = [i for i in range(combo.count()) if combo.itemData(i, HEADING_ROLE)]

        assert [combo.itemText(i) for i in headings] == ["GASTOS", "INGRESOS"]
        assert not any(combo.model().item(i).isEnabled() for i in headings)

    @pytest.mark.parametrize(
        ("name", "page_id"),
        [
            ("account_filter", PageId.ACCOUNTS),
            ("category_filter", PageId.CATEGORIES),
            ("payee_filter", PageId.PAYEES),
            ("tag_filter", PageId.TAGS),
        ],
    )
    def test_list_filters_end_with_edit_that_leads_to_their_page(
        self, qtbot, services, page, pesos, name, page_id
    ):
        services.payees.create("Kiosco")
        services.tags.create("Viaje")
        page.refresh()
        combo = getattr(page, name)
        last = combo.count() - 1
        before = combo.currentIndex()

        assert combo.itemText(last) == "Editar"
        assert combo.itemData(last, MANAGE_ROLE)
        with qtbot.waitSignal(page.navigate_requested) as signal:
            combo.view().pressed.emit(combo.model().index(last, 0))

        assert signal.args == [page_id]
        assert combo.currentIndex() == before

    def test_edit_row_is_never_selected(self, services, page, pesos):
        page.refresh()
        combo = page.account_filter

        combo.select(None)  # the "any" item
        assert combo.currentIndex() == 0
        combo.select(12345)  # an id that is not there falls back to the first choice
        assert combo.currentIndex() == 0
        page.refresh()  # refilling keeps a single «Editar» at the end
        assert [combo.itemText(i) for i in range(combo.count())].count("Editar") == 1

    def test_type_filter_has_no_edit_row(self, page):
        page.refresh()
        texts = [page.type_filter.itemText(i) for i in range(page.type_filter.count())]

        assert "Editar" not in texts

    def test_account_filter_still_shows_both_ends_of_transfer(self, services, page, pesos, dollars):
        populate(services, pesos, dollars)
        page.refresh()

        page.account_filter.select(dollars.id)

        assert column(page, AMOUNT) == ["$ 121.550,00 → US$ 100,00"]

    def test_delete_key_deletes_the_selected_row(
        self, qtbot, monkeypatch, services, event_bus, page, pesos, dollars
    ):
        populate(services, pesos, dollars)
        page.refresh()
        monkeypatch.setattr(transactions_page, "confirm", lambda *_args: True)

        qtbot.keyClick(page.table, Qt.Key.Key_Delete)  # nothing selected: nothing happens
        assert len(all_transactions(services)) == 5
        page.table.selectRow(column(page, AMOUNT).index("-$ 2.500,00"))
        with qtbot.waitSignal(event_bus.transactions_changed):
            qtbot.keyClick(page.table, Qt.Key.Key_Delete)

        assert len(all_transactions(services)) == 4

    def test_delete_transfer_after_confirmation(
        self, qtbot, monkeypatch, services, event_bus, page, pesos, dollars
    ):
        buy_dollars(services, pesos, dollars)
        page.refresh()
        monkeypatch.setattr(transactions_page, "confirm", lambda *_args: True)

        with qtbot.waitSignal(event_bus.transactions_changed):
            run_action(page.row_actions(0), "Eliminar")

        assert all_transactions(services) == []
        assert page.model.rowCount() == 0

    def test_payee_column_filter_and_search(self, services, page, pesos):
        for amount, payee in [("100", "Coto"), ("200", "Verdulería"), ("300", "")]:
            services.transactions.create(
                expense_draft(services, pesos.id, ars(amount), date(2026, 11, 3), payee_name=payee)
            )
        page.refresh()
        assert sorted(column(page, PAYEE)) == ["", "Coto", "Verdulería"]

        page.payee_filter.select(services.payees.find("Coto").id)
        assert column(page, AMOUNT) == ["-$ 100,00"]
        assert page.clear_filters_button.isEnabled()

        page.clear_filters_button.click()
        page.search_input.setText("verduleria")
        assert column(page, AMOUNT) == ["-$ 200,00"]

    def test_row_menu_offers_what_the_row_allows(self, services, page, pesos, dollars):
        populate(services, pesos, dollars)
        page.refresh()

        assert texts(page.row_actions(0)) == ["Editar", "Eliminar"]  # the transfer
        assert texts(page.row_actions(1)) == ["Editar", "Cambiar categoría", "Eliminar"]

    def test_selection_bar_takes_the_header_with_two_rows(self, services, page, pesos, dollars):
        populate(services, pesos, dollars)
        page.refresh()
        page.show()

        page.table.selectRow(1)
        assert not page.selection_bar.isVisible()
        assert page.export_button.isVisible()

        page.table.toggle_row(2)
        assert page.selection_bar.isVisible()
        assert not page.export_button.isVisible()
        assert page.selection_bar.count_label.text() == "2 seleccionadas"
        assert page.selection_bar.detail_label.text() == (
            "Ingresos $ 900.000,00 · Gastos $ 2.500,00 · Neto $ 897.500,00"
        )
        assert not page.category_button.isEnabled()  # an expense and an income

        page.selection_bar.clear_button.click()
        assert not page.selection_bar.isVisible()
        assert page.export_button.isVisible()

    def test_check_boxes_add_rows_and_the_header_box_chooses_all(
        self, qtbot, services, page, pesos, dollars
    ):
        populate(services, pesos, dollars)
        page.refresh()
        page.show()
        table = page.table

        for row in (0, 2):
            box = table.check_rect(table.visualRect(table.model().index(row, 0)))
            qtbot.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=box.center())

        assert table.selected_rows() == [0, 2]
        assert table.check_state() == Qt.CheckState.PartiallyChecked
        table.toggle_all()
        assert table.check_state() == Qt.CheckState.Checked
        table.toggle_all()
        assert table.selected_rows() == []

    def test_deletes_several_after_one_confirmation(
        self, qtbot, monkeypatch, services, event_bus, page, pesos, dollars
    ):
        populate(services, pesos, dollars)
        page.refresh()
        warnings = []
        monkeypatch.setattr(
            transactions_page, "confirm", lambda _p, _t, text: warnings.append(text) or True
        )
        page.table.selectRow(0)
        page.table.toggle_row(1)

        with qtbot.waitSignal(event_bus.transactions_changed):
            qtbot.keyClick(page.table, Qt.Key.Key_Delete)

        assert warnings == [
            "Se van a eliminar 2 transacciones. Las transferencias se eliminan con el"
            " movimiento de las dos cuentas."
        ]
        assert column(page, AMOUNT) == ["$ 900.000,00"]

    def test_changes_the_category_of_several(self, qtbot, services, event_bus, page, pesos):
        ids = [
            services.transactions.create(expense_draft(services, pesos.id, ars(a))).id
            for a in ("10", "20")
        ]
        ocio = category_id(services, "Ocio", TransactionType.EXPENSE)
        dialog = ChangeCategoryDialog(services, event_bus, ids, TransactionType.EXPENSE)
        qtbot.addWidget(dialog)
        dialog.category_input.select(ocio)

        with qtbot.waitSignal(event_bus.transactions_changed):
            dialog.save_button.click()

        assert {services.transactions.get(i).category_id for i in ids} == {ocio}


class TestAddTransactionButton:
    def test_without_accounts_leads_to_accounts_page(self, monkeypatch, window):
        messages = []
        monkeypatch.setattr(
            main_window_module.QMessageBox, "information", lambda *args: messages.append(args)
        )

        window.top_bar.add_transaction_requested.emit()

        assert len(messages) == 1
        assert window.current_page is window.page(PageId.ACCOUNTS)

    def test_with_accounts_opens_dialog(self, monkeypatch, window, pesos):
        opened = []
        monkeypatch.setattr(TransactionDialog, "exec", lambda dialog: opened.append(dialog))

        window.top_bar.add_transaction_requested.emit()

        assert len(opened) == 1


def test_export_saves_what_is_shown(monkeypatch, tmp_path, services, window, pesos):
    # Today, so it falls in the month the page opens on.
    services.transactions.create(expense_draft(services, pesos.id, ars("10"), date.today()))
    target = tmp_path / "out.csv"
    suggested = []

    def save_dialog(_parent, _title, path, _filter):
        suggested.append(path)
        return str(target), ""

    monkeypatch.setattr(export.QFileDialog, "getSaveFileName", save_dialog)
    page = window.page(PageId.TRANSACTIONS)
    window.show_page(PageId.TRANSACTIONS)

    page.export_button.click()

    assert target.read_text(encoding="utf-8-sig").count("\n") == 2
    month = page.period_selector.period().start
    assert suggested[0].endswith(f"nodus-transacciones-{month:%Y-%m}.csv")


def test_payee_opens_its_whole_history(qtbot, services, window, pesos):
    services.transactions.create(
        expense_draft(services, pesos.id, ars("10"), date(2026, 3, 5), payee_name="Coto")
    )
    services.transactions.create(
        expense_draft(services, pesos.id, ars("20"), date(2026, 3, 6), payee_name="Día")
    )
    window.show_page(PageId.PAYEES)
    payees = window.page(PageId.PAYEES)
    coto_row = next(
        row for row in range(payees.proxy.rowCount())
        if payees.proxy.index(row, 0).data() == "Coto"
    )  # fmt: skip

    run_action(payees.row_actions(coto_row), "Ver movimientos")

    transactions = window.page(PageId.TRANSACTIONS)
    assert window.current_page is transactions
    assert transactions.period_selector.period().start == date(2026, 3, 1)
    assert transactions.payee_filter.current_id() == services.payees.find("Coto").id
    assert column(transactions, AMOUNT) == ["-$ 10,00"]
