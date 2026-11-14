"""Purchases in installments on screen: the form, the list, Recurrentes and the account.

Besides what each screen should show, these tests try what a hurried user would do:
switch the amount back and forth, change the kind of movement, double-click a row.
"""

from datetime import date

import pytest
from factories import ars, category_id, expense_draft, light_theme
from menus import double_click_row, main_action, run_action, texts
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from nodus.models.installment_plan import InstallmentPlan
from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.ui.dialogs.installment_fields import PER_INSTALLMENT, TOTAL
from nodus.ui.dialogs.transaction_dialog import (
    EXPENSE_MODE,
    INCOME_MODE,
    TRANSFER_MODE,
    TransactionDialog,
)
from nodus.ui.formatting import format_date
from nodus.ui.navigation import DetailId
from nodus.ui.pages import transaction_list_view
from nodus.ui.pages.dashboard_cards import LatestTransactionRow, LatestTransactionsCard
from nodus.ui.pages.recurring_page import RecurringPage
from nodus.ui.pages.transactions_page import TransactionsPage
from nodus.ui.widgets.transaction_table import AMOUNT, DATE, DESCRIPTION

TODAY = date.today()


def make_dialog(qtbot, services, event_bus, transaction=None) -> TransactionDialog:
    dialog = TransactionDialog(services, event_bus, light_theme(), transaction)
    qtbot.addWidget(dialog)
    return dialog


def save(qtbot, dialog) -> None:
    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)


def fill(dialog, amount: str, count: int, note: str = "Heladera") -> None:
    """A purchase ready to save: the category starts empty, so any one is picked."""
    dialog.amount_input.line_edit.setText(amount)
    dialog.installment_fields.set_count(count)
    dialog.category_input.setCurrentIndex(0)
    dialog.note_input.setText(note)


def label_of(dialog, field: QWidget) -> str:
    return dialog.form.labelForField(field).text()


def hint_shown(dialog) -> str | None:
    """The text under the amount, if its row is shown."""
    hint = dialog.installments_hint
    return None if hint.isHidden() else hint.text()


def all_transactions(services):
    return services.transactions.list_transactions(TransactionFilter())


def plan_count(services) -> int:
    connection = services.transactions._database.connection
    return connection.execute("SELECT COUNT(*) FROM installment_plans").fetchone()[0]


@pytest.fixture
def heladera(services, pesos):
    """$ 75.000 in 6 installments, the first one today: five still to come."""
    draft = expense_draft(services, pesos.id, ars("75000"), TODAY, note="Heladera")
    return services.installments.create(draft, InstallmentPlan(None, 6, ars("75000"), TODAY))


def first_installment(services, plan):
    found = services.transactions.list_transactions(TransactionFilter(installment_plan_id=plan.id))
    return next(t for t in found if t.installment.number == 1)


class TestDialog:
    def test_the_row_is_there_only_for_an_expense(self, qtbot, services, event_bus, pesos):
        dialog = make_dialog(qtbot, services, event_bus)
        fields = dialog.installment_fields

        assert dialog.form.isRowVisible(fields)
        for mode in (INCOME_MODE, TRANSFER_MODE):
            dialog.mode_input.set_index(mode)
            assert not dialog.form.isRowVisible(fields)
        dialog.mode_input.set_index(EXPENSE_MODE)
        assert dialog.form.isRowVisible(fields)

    def test_how_it_is_paid_comes_before_how_much(self, qtbot, services, event_bus, pesos):
        dialog = make_dialog(qtbot, services, event_bus)
        row = dialog.form.getWidgetPosition

        assert row(dialog.account_input)[0] < row(dialog.installment_fields)[0]
        assert row(dialog.installment_fields)[0] < row(dialog.amount_row)[0]
        assert dialog.installments_hint.parent() is dialog.amount_row  # right under it

    def test_a_single_payment_reads_as_a_plain_expense(self, qtbot, services, event_bus, pesos):
        dialog = make_dialog(qtbot, services, event_bus)
        dialog.amount_input.line_edit.setText("75.000")
        fields = dialog.installment_fields

        assert fields.count_input.currentText() == "1 pago"
        assert fields.amount_mode.isHidden()
        assert fields.other_input.isHidden()
        assert not hint_shown(dialog)
        assert label_of(dialog, dialog.amount_row) == "Monto"
        assert label_of(dialog, dialog.date_input) == "Fecha"

    def test_the_list_is_short_and_plain(self, qtbot, services, event_bus, pesos):
        dialog = make_dialog(qtbot, services, event_bus)
        dialog.amount_input.line_edit.setText("75.000")
        combo = dialog.installment_fields.count_input

        shown = [combo.itemText(i) for i in range(combo.count()) if combo.itemText(i)]
        assert shown == [
            "1 pago",
            "3 cuotas",
            "6 cuotas",
            "9 cuotas",
            "12 cuotas",
            "18 cuotas",
            "Otra cantidad…",
        ]

    def test_the_hint_under_the_amount_says_what_each_is_and_when_the_last_comes(
        self, qtbot, services, event_bus, pesos
    ):
        dialog = make_dialog(qtbot, services, event_bus)
        dialog.date_input.set_day(date(2026, 11, 10))
        fill(dialog, "75.000", 6)
        fields = dialog.installment_fields

        assert not fields.amount_mode.isHidden()
        assert hint_shown(dialog) == "6 cuotas de $ 12.500,00 · la última, el 10/04/2027"
        assert label_of(dialog, dialog.amount_row) == "Total"
        assert label_of(dialog, dialog.date_input) == "Primera cuota"

        fields.amount_mode.set_index(PER_INSTALLMENT)
        assert hint_shown(dialog) == "Total $ 450.000,00 · la última, el 10/04/2027"
        assert label_of(dialog, dialog.amount_row) == "Cuota"

    def test_an_uneven_total_says_the_first_installment_takes_the_cents(
        self, qtbot, services, event_bus, pesos
    ):
        dialog = make_dialog(qtbot, services, event_bus)
        dialog.date_input.set_day(date(2026, 1, 31))
        fill(dialog, "100", 3)

        assert hint_shown(dialog) == (
            "3 cuotas de $ 33,33 (la primera, $ 33,34) · la última, el 31/03/2026"
        )

    def test_no_hint_while_the_amount_cannot_be_split(self, qtbot, services, event_bus, pesos):
        dialog = make_dialog(qtbot, services, event_bus)
        fill(dialog, "0,05", 6)
        assert not hint_shown(dialog)
        dialog.amount_input.line_edit.setText("")
        assert not hint_shown(dialog)

    def test_no_hint_in_another_kind_of_movement(self, qtbot, services, event_bus, pesos):
        dialog = make_dialog(qtbot, services, event_bus)
        fill(dialog, "75.000", 6)

        dialog.mode_input.set_index(INCOME_MODE)

        assert not hint_shown(dialog)
        assert dialog.installment_fields.amount_mode.isHidden()
        assert label_of(dialog, dialog.amount_row) == "Monto"

    def test_switching_total_and_per_installment_never_rewrites_the_amount(
        self, qtbot, services, event_bus, pesos
    ):
        dialog = make_dialog(qtbot, services, event_bus)
        fill(dialog, "100", 3)
        fields = dialog.installment_fields

        for _ in range(5):
            fields.amount_mode.set_index(PER_INSTALLMENT)
            fields.amount_mode.set_index(TOTAL)
        assert dialog.amount_input.line_edit.text() == "100"
        save(qtbot, dialog)

        assert sum((t.amount for t in all_transactions(services)), ars("0")) == ars("100")

    def test_a_click_anywhere_on_the_list_opens_it(self, qtbot, services, event_bus, pesos):
        dialog = make_dialog(qtbot, services, event_bus)
        dialog.show()
        qtbot.waitExposed(dialog)
        combo = dialog.installment_fields.count_input

        qtbot.mouseClick(combo, Qt.MouseButton.LeftButton, pos=combo.rect().center())

        qtbot.waitUntil(lambda: combo.view().isVisible())
        combo.hidePopup()

    def test_typing_a_number_picks_it(self, qtbot, services, event_bus, pesos):
        dialog = make_dialog(qtbot, services, event_bus)

        qtbot.keyClicks(dialog.installment_fields.count_input, "12")

        assert dialog.installment_fields.count == 12

    def test_another_count_is_typed_beside_the_list(self, qtbot, services, event_bus, pesos):
        dialog = make_dialog(qtbot, services, event_bus)
        dialog.amount_input.line_edit.setText("75.000")
        fields = dialog.installment_fields
        combo = fields.count_input

        combo.setCurrentIndex(combo.findText("Otra cantidad…"))
        assert not fields.other_input.isHidden()
        assert fields.count is None
        assert not fields.amount_mode.isHidden()  # installments, the count still to come
        assert not hint_shown(dialog)
        qtbot.keyClicks(fields.other_input, "10")

        assert hint_shown(dialog).startswith("10 cuotas de $ 7.500,00 · ")
        dialog.category_input.setCurrentIndex(0)
        save(qtbot, dialog)
        assert len(all_transactions(services)) == 10

    @pytest.mark.parametrize("typed", ["", "0", "73"])
    def test_another_count_out_of_range_is_not_saved(
        self, qtbot, services, event_bus, pesos, typed
    ):
        dialog = make_dialog(qtbot, services, event_bus)
        dialog.amount_input.line_edit.setText("75.000")
        dialog.category_input.setCurrentIndex(0)
        fields = dialog.installment_fields
        fields.count_input.setCurrentIndex(fields.count_input.findText("Otra cantidad…"))
        fields.other_input.setText(typed)

        save(qtbot, dialog)

        assert dialog.field_error(fields.other_input) == "Escribe en cuántas cuotas, de 2 a 72."
        assert all_transactions(services) == []

    def test_a_purchase_with_a_count_not_offered_opens_with_it(
        self, qtbot, services, event_bus, pesos
    ):
        draft = expense_draft(services, pesos.id, ars("40000"), TODAY, note="Auto")
        plan = services.installments.create(draft, InstallmentPlan(None, 40, ars("40000"), TODAY))
        dialog = make_dialog(qtbot, services, event_bus, first_installment(services, plan))
        fields = dialog.installment_fields

        assert fields.count_input.currentText() == "Otra cantidad…"
        assert fields.other_input.text() == "40"
        save(qtbot, dialog)
        assert len(all_transactions(services)) == 40

    def test_the_dialog_keeps_its_width(self, qtbot, services, event_bus, pesos, dollars):
        dialog = make_dialog(qtbot, services, event_bus)
        dialog.amount_input.line_edit.setText("75.000")
        dialog.show()
        qtbot.waitExposed(dialog)
        qtbot.wait(10)  # the layout applies its size on the next pass of the event loop
        width = dialog.width()

        for count in (6, 40):
            dialog.installment_fields.set_count(count)
            qtbot.wait(10)
            assert dialog.width() == width
        for mode in (INCOME_MODE, TRANSFER_MODE, EXPENSE_MODE):
            dialog.mode_input.set_index(mode)
            qtbot.wait(10)
            assert dialog.width() == width

    def test_saves_six_installments_the_first_today(self, qtbot, services, event_bus, pesos):
        dialog = make_dialog(qtbot, services, event_bus)
        fill(dialog, "75.000", 6)

        with qtbot.waitSignal(event_bus.transactions_changed):
            save(qtbot, dialog)

        saved = sorted(all_transactions(services), key=lambda t: t.occurred_on)
        assert [t.installment.label for t in saved] == [f"{n}/6" for n in range(1, 7)]
        assert saved[0].occurred_on == TODAY
        assert {t.amount for t in saved} == {ars("12500")}
        # Only today's installment has come off the account.
        assert services.accounts.balance(pesos.id) == ars("87500")

    def test_per_installment_saves_that_amount_each_time(self, qtbot, services, event_bus, pesos):
        dialog = make_dialog(qtbot, services, event_bus)
        fill(dialog, "13.000", 6)
        dialog.installment_fields.amount_mode.set_index(PER_INSTALLMENT)

        save(qtbot, dialog)

        assert {t.amount for t in all_transactions(services)} == {ars("13000")}

    def test_one_installment_creates_no_plan(self, qtbot, services, event_bus, pesos):
        dialog = make_dialog(qtbot, services, event_bus)
        fill(dialog, "75.000", 6)
        dialog.installment_fields.set_count(1)

        save(qtbot, dialog)

        [saved] = all_transactions(services)
        assert saved.installment is None
        assert saved.amount == ars("75000")
        assert plan_count(services) == 0

    @pytest.mark.parametrize("mode", [INCOME_MODE, TRANSFER_MODE])
    def test_another_kind_ignores_the_installments_left_typed(
        self, qtbot, services, event_bus, pesos, dollars, mode
    ):
        dialog = make_dialog(qtbot, services, event_bus)
        fill(dialog, "75.000", 6)
        dialog.account_input.select(pesos.id)  # two accounts, none used yet
        dialog.mode_input.set_index(mode)
        if mode == TRANSFER_MODE:
            dialog.to_account_input.select(dollars.id)
            dialog.amount_in_input.line_edit.setText("50")
        else:  # an expense category no longer fits
            dialog.category_input.select(category_id(services, "Sueldo", TransactionType.INCOME))

        save(qtbot, dialog)

        saved = all_transactions(services)
        assert saved, dialog.error_label.text()
        assert all(t.installment is None for t in saved)
        assert plan_count(services) == 0
        assert len(saved) == (2 if mode == TRANSFER_MODE else 1)

    def test_too_small_an_amount_keeps_the_dialog_open(self, qtbot, services, event_bus, pesos):
        dialog = make_dialog(qtbot, services, event_bus)
        fill(dialog, "0,05", 6)

        save(qtbot, dialog)

        assert dialog.field_error(dialog.amount_input) == (
            "El monto no alcanza para 6 cuotas de al menos un centavo."
        )
        assert all_transactions(services) == []

    def test_any_installment_opens_the_whole_purchase(self, qtbot, services, event_bus, heladera):
        found = services.transactions.list_transactions(
            TransactionFilter(installment_plan_id=heladera.id)
        )
        fourth = next(t for t in found if t.installment.number == 4)

        dialog = make_dialog(qtbot, services, event_bus, fourth)

        assert dialog.amount_input.line_edit.text() == "75.000,00"
        assert dialog.installment_fields.count == 6
        assert dialog.date_input.day() == TODAY  # the first installment, not the fourth
        assert label_of(dialog, dialog.amount_row) == "Total"
        assert not dialog.mode_input.buttons[INCOME_MODE].isEnabled()

    def test_editing_the_purchase_rewrites_its_installments(
        self, qtbot, services, event_bus, heladera
    ):
        dialog = make_dialog(qtbot, services, event_bus, first_installment(services, heladera))
        dialog.installment_fields.set_count(3)
        dialog.note_input.setText("Heladera nueva")

        save(qtbot, dialog)

        saved = sorted(all_transactions(services), key=lambda t: t.installment.number)
        assert [t.installment.label for t in saved] == ["1/3", "2/3", "3/3"]
        assert {t.amount for t in saved} == {ars("25000")}
        assert {t.note for t in saved} == {"Heladera nueva"}

    def test_opening_and_saving_untouched_changes_nothing(
        self, qtbot, services, event_bus, heladera
    ):
        before = sorted(all_transactions(services), key=lambda t: t.id)

        save(qtbot, make_dialog(qtbot, services, event_bus, first_installment(services, heladera)))

        assert sorted(all_transactions(services), key=lambda t: t.id) == before

    def test_down_to_one_installment_it_becomes_a_plain_expense(
        self, qtbot, services, event_bus, heladera
    ):
        dialog = make_dialog(qtbot, services, event_bus, first_installment(services, heladera))
        dialog.installment_fields.set_count(1)

        save(qtbot, dialog)

        [saved] = all_transactions(services)
        assert saved.installment is None
        assert saved.amount == ars("75000")
        assert plan_count(services) == 0

    def test_a_plain_expense_can_be_turned_into_installments(
        self, qtbot, services, event_bus, pesos
    ):
        expense = services.transactions.create(
            expense_draft(services, pesos.id, ars("75000"), TODAY, note="Heladera")
        )
        dialog = make_dialog(qtbot, services, event_bus, expense)
        assert dialog.form.isRowVisible(dialog.installment_fields)
        dialog.installment_fields.set_count(6)

        save(qtbot, dialog)

        saved = {t.id: t for t in all_transactions(services)}
        assert len(saved) == 6
        assert saved[expense.id].installment.number == 1  # the same row, now the first


@pytest.fixture
def page(qtbot, services, event_bus, theme_manager) -> TransactionsPage:
    transactions = TransactionsPage(services, event_bus, theme_manager)
    qtbot.addWidget(transactions)
    month = Month.of(TODAY)
    transactions.period_selector.set_period(Period.of_months(month, month.shifted(6)))
    transactions.refresh()
    return transactions


def column(page, index: int, role=Qt.ItemDataRole.DisplayRole) -> list:
    model = page.model
    return [model.data(model.index(row, index), role) for row in range(model.rowCount())]


def row_of(page, label: str) -> int:
    return next(i for i, text in enumerate(column(page, DESCRIPTION)) if text.endswith(label))


class TestTransactionsList:
    def test_each_installment_says_which_it_is(self, heladera, page):
        assert sorted(column(page, DESCRIPTION)) == sorted(f"Heladera · {n}/6" for n in range(1, 7))

    def test_those_still_to_come_are_dimmed_and_say_when(self, theme_manager, heladera, page):
        model = page.model
        today_row, later_row = row_of(page, "1/6"), row_of(page, "2/6")
        muted = theme_manager.theme.text_muted
        foreground = Qt.ItemDataRole.ForegroundRole

        for index in (DATE, DESCRIPTION, AMOUNT):
            assert model.data(model.index(later_row, index), foreground).name() == muted
        assert model.data(model.index(today_row, AMOUNT), foreground).name() != muted
        second = model.item(later_row).occurred_on
        for index in (DATE, AMOUNT):
            tooltip = model.data(model.index(later_row, index), Qt.ItemDataRole.ToolTipRole)
            assert tooltip == f"Se descuenta el {format_date(second)}"
        assert model.item(later_row).upcoming
        assert not model.item(today_row).upcoming

    def test_the_menu_edits_pays_off_and_deletes_the_purchase(self, heladera, page):
        actions = page.list_view.row_actions(row_of(page, "3/6"))

        assert texts(actions) == [
            "Editar compra",
            "Adelantar las cuotas que faltan",
            "Eliminar compra",
        ]
        assert main_action(actions) == "Editar compra"
        assert not next(a for a in actions if a.destructive).default

    def test_a_plain_expense_keeps_its_menu(self, services, page, pesos):
        services.transactions.create(expense_draft(services, pesos.id, ars("10"), TODAY))
        page.refresh()

        assert texts(page.list_view.row_actions(0)) == ["Editar", "Eliminar"]

    def test_a_double_click_opens_the_purchase_and_never_deletes(
        self, monkeypatch, services, heladera, page
    ):
        opened, asked = [], []
        monkeypatch.setattr(TransactionDialog, "exec", lambda dialog: opened.append(dialog))
        monkeypatch.setattr(transaction_list_view, "confirm", lambda *args: asked.append(args))
        page.show()

        double_click_row(page.list_view.table, row_of(page, "5/6"))

        assert len(opened) == 1
        assert opened[0].installment_fields.count == 6
        assert asked == []
        assert len(all_transactions(services)) == 6

    def test_paying_off_brings_the_rest_to_today_and_can_be_undone(
        self, services, pesos, heladera, page
    ):
        before = [t.occurred_on for t in all_transactions(services)]
        run_action(
            page.list_view.row_actions(row_of(page, "2/6")), "Adelantar las cuotas que faltan"
        )

        assert {t.occurred_on for t in all_transactions(services)} == {TODAY}
        assert services.accounts.balance(pesos.id) == ars("25000")
        page.refresh()
        actions = page.list_view.row_actions(row_of(page, "2/6"))
        assert "Deshacer adelanto" in texts(actions)

        run_action(actions, "Deshacer adelanto")
        assert [t.occurred_on for t in all_transactions(services)] == before
        assert services.accounts.balance(pesos.id) == ars("87500")

    def test_the_warning_names_the_purchase_and_its_installments(
        self, monkeypatch, services, heladera, page
    ):
        warnings = []
        monkeypatch.setattr(
            transaction_list_view, "confirm", lambda _p, _t, text: warnings.append(text) or True
        )

        run_action(page.list_view.row_actions(row_of(page, "4/6")), "Eliminar compra")

        assert warnings == ["Se van a eliminar las 6 cuotas de «Heladera»."]
        assert all_transactions(services) == []
        assert plan_count(services) == 0

    def test_deleting_several_with_an_installment_says_its_purchase_goes(
        self, monkeypatch, services, pesos, heladera, page
    ):
        services.transactions.create(expense_draft(services, pesos.id, ars("10"), TODAY))
        page.refresh()
        warnings = []
        monkeypatch.setattr(
            transaction_list_view, "confirm", lambda _p, _t, text: warnings.append(text) or True
        )
        items = [page.model.item(row_of(page, "2/6")), page.model.item(row_of(page, "3/6"))]
        plain = page.model.item(
            next(i for i, d in enumerate(column(page, DESCRIPTION)) if "/" not in d)
        )

        transaction_list_view.delete_transactions(
            services, page.list_view._event_bus, [*items, plain], page
        )

        assert warnings[0].endswith(" Las cuotas se eliminan con toda su compra.")
        assert all_transactions(services) == []


class TestDashboard:
    def test_latest_transactions_shows_nothing_still_to_come(
        self, qtbot, services, theme_manager, heladera
    ):
        card = LatestTransactionsCard(services, theme_manager)
        qtbot.addWidget(card)
        month = Month.of(TODAY)

        card.show_period(Period.of_months(month, month.shifted(6)))

        rows = card.findChildren(LatestTransactionRow)
        assert [row.item.transaction.installment.number for row in rows] == [1]


@pytest.fixture
def recurring(qtbot, services, event_bus) -> RecurringPage:
    recurring = RecurringPage(services, event_bus, light_theme())
    qtbot.addWidget(recurring)
    return recurring


class TestRecurring:
    def test_a_purchase_alone_is_enough_to_leave_the_empty_state(
        self, services, recurring, heladera
    ):
        recurring.refresh(TODAY)

        [row] = recurring.installment_rows
        assert row.title_label.text() == "Heladera"
        assert row.detail_label.text().startswith("1 de 6 · ")
        assert row.amount_label.text() == "$ 12.500,00"
        assert recurring.installments_label.text() == "$ 12.500,00"

    def test_its_menu_is_the_one_of_the_list(self, recurring, heladera):
        recurring.refresh(TODAY)

        actions = recurring.installment_rows[0].more_button._actions_for()
        assert texts(actions) == [
            "Editar compra",
            "Adelantar las cuotas que faltan",
            "Eliminar compra",
        ]
        assert main_action(actions) == "Editar compra"

    def test_a_finished_purchase_leaves_the_group(self, services, recurring, heladera):
        services.installments.settle(heladera.id, TODAY)

        recurring.refresh(TODAY)

        assert recurring.installment_rows == []

    def test_follows_changes_to_the_transactions(self, services, event_bus, recurring, pesos):
        recurring.refresh(TODAY)
        assert recurring.installment_rows == []
        draft = expense_draft(services, pesos.id, ars("1000"), TODAY, note="Silla")
        services.installments.create(draft, InstallmentPlan(None, 2, ars("1000"), TODAY))

        event_bus.transactions_changed.emit()

        assert [row.title_label.text() for row in recurring.installment_rows] == ["Silla"]


class TestAccountDetail:
    def test_shows_what_is_still_to_pay(self, services, window, pesos, dollars, heladera):
        window.show_detail(DetailId.ACCOUNT, pesos.id)
        detail = window.detail(DetailId.ACCOUNT)

        assert not detail.pending_tile.isHidden()
        assert detail.pending_label.text() == "$ 62.500,00"
        assert " cuotas · hasta " in detail.pending_note.text()
        assert detail.balance_label.text() == "$ 87.500,00"
        window.show_detail(DetailId.ACCOUNT, dollars.id)
        assert detail.pending_tile.isHidden()


def test_an_expense_category_is_kept_on_every_installment(qtbot, services, event_bus, pesos):
    dialog = make_dialog(qtbot, services, event_bus)
    fill(dialog, "6.000", 3)
    dialog.category_input.select(category_id(services, "Ocio", TransactionType.EXPENSE))

    save(qtbot, dialog)

    ocio = category_id(services, "Ocio", TransactionType.EXPENSE)
    assert {t.category_id for t in all_transactions(services)} == {ocio}
