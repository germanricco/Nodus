"""Nodus from start to finish, through the dialogs, over a file that is reopened: the v0.1
scenario, then one per area (budgets, charges, installments, refunds, goals, groups,
undoing, copies)."""

from datetime import date

import pytest
from factories import ars, category_id, light_theme, services_for, usd
from journeys import Journey
from menus import run_action
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from nodus.database.database import Database
from nodus.models.currency import Currency
from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.ui.actions.accounts import delete_account
from nodus.ui.dialogs import confirm as confirm_dialog
from nodus.ui.dialogs import restore_copy
from nodus.ui.dialogs.account_dialog import AccountDialog
from nodus.ui.dialogs.budget_dialog import BudgetDialog
from nodus.ui.dialogs.goal_dialog import GoalDialog
from nodus.ui.dialogs.recurring_charge_dialog import PayChargeDialog, RecurringChargeDialog
from nodus.ui.dialogs.refund_extra_dialog import RefundExtraDialog
from nodus.ui.dialogs.refund_picker import RefundPickerDialog
from nodus.ui.dialogs.transaction_dialog import (
    EXPENSE_MODE,
    INCOME_MODE,
    TRANSFER_MODE,
    TransactionDialog,
)
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import PageId
from nodus.ui.pages.settings.general_card import THEME_MODES
from nodus.ui.shell.main_window import MainWindow
from nodus.ui.theme.theme import ThemeMode
from nodus.ui.widgets.tables.transaction_table import MOVEMENT

EXPENSE, INCOME = TransactionType.EXPENSE, TransactionType.INCOME
FOOD = "Supermercado y comida"


def fill_and_save(qtbot, dialog) -> None:
    qtbot.addWidget(dialog)
    dialog.save_button.click()
    assert not dialog.error_label.isVisibleTo(dialog), dialog.error_label.text()


def create_account(qtbot, services, event_bus, name: str, currency: Currency, balance: str):
    dialog = AccountDialog(services, event_bus)
    dialog.name_input.setText(name)
    dialog.currency_input.setCurrentIndex(dialog.currency_input.findData(currency))
    dialog.balance_input.line_edit.setText(balance)
    fill_and_save(qtbot, dialog)
    return next(a for a in services.accounts.list_accounts() if a.name == name)


def record(qtbot, services, event_bus, mode: int, **fields) -> None:
    dialog = TransactionDialog(services, event_bus, light_theme())
    dialog.mode_input.set_index(mode)
    dialog.account_input.select(fields["account"].id)
    if "to_account" in fields:
        dialog.to_account_input.select(fields["to_account"].id)
        dialog.amount_in_input.line_edit.setText(fields["amount_in"])
    if "category" in fields:
        dialog.category_input.setCurrentIndex(dialog.category_input.findText(fields["category"]))
    dialog.amount_input.line_edit.setText(fields["amount"])
    fill_and_save(qtbot, dialog)


def test_first_month_with_nodus(qtbot, qapp, tmp_path):
    today = date.today()
    database = Database.open(tmp_path / "nodus.db")
    services, event_bus = services_for(database), EventBus()
    services.settings.set_tour_offered(True)  # its offer is a question of its own test
    theme_manager = light_theme()
    window = MainWindow(services, event_bus, theme_manager)
    qtbot.addWidget(window)

    banco = create_account(qtbot, services, event_bus, "Banco", Currency.ARS, "100.000")
    ahorro = create_account(qtbot, services, event_bus, "Ahorro", Currency.USD, "500")
    window.show_page(PageId.SETTINGS)
    settings = window.page(PageId.SETTINGS)
    settings.rates.rate_value_input.line_edit.setText("1.200")
    settings.rates.save_rate_button.click()
    record(qtbot, services, event_bus, INCOME_MODE, account=banco, amount="900.000",
           category="Sueldo")  # fmt: skip
    record(qtbot, services, event_bus, EXPENSE_MODE, account=banco, amount="85.000,50",
           category="Supermercado y comida")  # fmt: skip
    record(qtbot, services, event_bus, TRANSFER_MODE, account=banco, to_account=ahorro,
           amount="240.000", amount_in="200")  # fmt: skip
    settings.general.theme_input.set_index(THEME_MODES.index(ThemeMode.DARK))

    balances = services.accounts.balances()
    assert balances[banco.id] == ars("674999.50")
    assert balances[ahorro.id] == usd("700")
    summary = services.dashboard.summary(Period.of_months(Month.of(today)))
    assert (summary.income, summary.expenses) == (ars("900000"), ars("85000.50"))
    window.show_page(PageId.DASHBOARD)
    dashboard_texts = [label.text() for label in window.page(PageId.DASHBOARD).findChildren(QLabel)]
    assert "$ 814.999,50" in dashboard_texts  # the month's savings
    window.close()
    database.close()

    # Everything is still there after reopening the file.
    reopened = Database.open(tmp_path / "nodus.db")
    try:
        again = services_for(reopened)
        assert again.accounts.balances() == balances
        assert again.net_worth.net_worth(today).total_in[Currency.ARS] == ars("1514999.50")
        assert again.settings.theme_preference() == "dark"
        legs = again.transactions.list_transactions(TransactionFilter(is_transfer=True))
        assert {leg.type for leg in legs} == {TransactionType.INCOME, TransactionType.EXPENSE}
    finally:
        reopened.close()


# One scenario per area, each as a person goes through it: from the dialogs to what the
# other pages show, and to the file reopened (``journeys.Journey``).


@pytest.fixture
def journey(qtbot, tmp_path) -> Journey:
    return Journey(qtbot, tmp_path / "Nodus")


def test_a_budget_through_the_month(journey, monkeypatch):
    today = date.today()
    month = Month.of(today)
    banco = journey.account("Banco", "500.000")
    budgets = journey.show(PageId.BUDGETS)
    dialog = BudgetDialog(journey.services, journey.event_bus, month, parent=journey.window)
    dialog.category_input.select(category_id(journey.services, FOOD, EXPENSE))
    dialog.amount_input.line_edit.setText("100.000")
    journey.save(dialog)

    journey.spend(banco, "60.000", FOOD)
    journey.spend(banco, "55.000", FOOD)

    (budget,) = journey.services.budgets.month_budgets(month, today).budgets
    assert budget.spent == ars("115000")
    assert any("15.000" in text for text in journey.texts(budgets))  # over by $ 15.000
    titles = [notice.title for notice in journey.services.notifications.notices(today)]
    assert f"{FOOD} pasó su límite" in titles
    with journey.reopened() as again:
        # The limit goes on into the next month, until it is changed or removed.
        assert again.budgets.limits_on(month.next()) == {budget.category.id: ars("100000")}


def test_a_monthly_charge_paid_and_undone(journey):
    today = date.today()
    banco = journey.account("Banco", "100.000")
    dialog = RecurringChargeDialog(journey.services, journey.event_bus, parent=journey.window)
    dialog.name_input.setText("Internet")
    dialog.amount_input.line_edit.setText("15.000")
    dialog.category_input.select(category_id(journey.services, "Servicios", EXPENSE))
    dialog.due_input.set_day(today)
    journey.save(dialog)
    recurring = journey.show(PageId.RECURRING)
    (row,) = recurring.rows
    assert row.charge.name == "Internet"

    journey.save(
        PayChargeDialog(journey.services, journey.event_bus, row.charge, parent=journey.window)
    )

    assert journey.services.accounts.balance(banco.id) == ars("85000")
    assert journey.toasts()[-1] == "Se pagó Internet."
    (charge,) = journey.services.recurring.list_charges()
    assert charge.next_due_on > today
    assert "85.000,00" in " ".join(journey.texts(journey.window.sidebar))

    journey.window.activateWindow()
    journey.qtbot.waitUntil(journey.window.isActiveWindow)
    journey.qtbot.keyClick(journey.window, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)

    assert journey.toasts()[-1] == "Se deshizo."
    assert journey.services.accounts.balance(banco.id) == ars("100000")
    assert journey.services.recurring.get(charge.id).next_due_on == today
    assert "100.000,00" in " ".join(journey.texts(journey.window.sidebar))
    with journey.reopened() as again:
        assert again.transactions.list_transactions(TransactionFilter()) == []


def test_a_purchase_in_installments_and_its_deletion(journey, monkeypatch):
    banco = journey.account("Banco", "100.000")
    dialog = journey.transaction_dialog(EXPENSE_MODE, banco, "60.000")
    journey.pick_category(dialog, "Vivienda", EXPENSE)
    dialog.installment_fields.set_count(6)
    dialog.note_input.setText("Heladera")
    journey.save(dialog)

    installments = journey.services.transactions.list_transactions(TransactionFilter())
    assert sorted(t.amount for t in installments) == [ars("10000")] * 6
    assert journey.services.accounts.balance(banco.id) == ars("90000")  # the first, today
    transactions = journey.show(PageId.TRANSACTIONS)
    assert any("1/6" in text for text in journey.column(transactions, MOVEMENT))

    monkeypatch.setattr(confirm_dialog, "confirm", lambda *_args: True)
    run_action(transactions.row_actions(0), "Eliminar compra")  # all six go

    assert journey.services.transactions.list_transactions(TransactionFilter()) == []
    assert journey.services.accounts.balance(banco.id) == ars("100000")
    with journey.reopened() as again:
        assert again.transactions.list_transactions(TransactionFilter()) == []


def test_refunds_up_to_the_expense_and_past_it(journey, monkeypatch):
    banco = journey.account("Banco", "100.000")
    journey.spend(banco, "1.000", "Ropa", note="Zapatillas")
    (shoes,) = journey.services.transactions.list_transactions(TransactionFilter())

    def refund(amount: str) -> None:
        monkeypatch.setattr(RefundPickerDialog, "exec", lambda picker: picker_chooses(picker))
        dialog = journey.transaction_dialog(INCOME_MODE, banco, amount)
        journey.pick_category(dialog, "Reembolsos", INCOME)
        dialog.refund_input.choose()
        journey.save(dialog)

    def picker_chooses(picker) -> bool:
        picker.chosen = journey.services.transactions.get(shoes.id)
        return True

    refund("400")
    assert journey.services.refunds.summary(shoes.id).remaining == ars("600")

    offered = []

    def split(extra) -> int:
        offered.append(extra.category_input.currentText())
        extra.save_button.click()
        return extra.result()

    monkeypatch.setattr(RefundExtraDialog, "exec", split)
    refund("1.000")  # $ 600 were left: $ 400 too many

    assert offered == ["Otros"]
    summary = journey.services.refunds.summary(shoes.id)
    assert (summary.refunded, summary.remaining) == (ars("1000"), ars("0"))
    others = category_id(journey.services, "Otros", INCOME)
    incomes = journey.services.transactions.list_transactions(TransactionFilter(category_id=others))
    assert [t.amount for t in incomes] == [ars("400")]
    assert journey.services.accounts.balance(banco.id) == ars("100400")
    with journey.reopened() as again:
        assert again.refunds.summary(shoes.id).refunded == ars("1000")


def test_a_goal_grows_with_its_account(journey):
    today = date.today()
    ahorro = journey.account("Ahorro", "500", Currency.USD)
    dialog = GoalDialog(journey.services, journey.event_bus, today=today, parent=journey.window)
    dialog.name_input.setText("Viaje")
    dialog.currency_input.setCurrentIndex(dialog.currency_input.findData(Currency.USD))
    dialog.target_input.line_edit.setText("2.000")
    dialog.shares_input.row_for(ahorro.id).check.setChecked(True)
    journey.save(dialog)
    goals = journey.show(PageId.GOALS)
    assert any("25 %" in text for text in journey.texts(goals)), journey.texts(goals)

    journey.earn(ahorro, "500", "Sueldo")

    (goal,) = journey.services.goals.list_goals()
    assert journey.services.goals.progress(goal, today).percent == 50
    assert any("50 %" in text for text in journey.texts(goals)), journey.texts(goals)
    with journey.reopened() as again:
        assert again.goals.progress(again.goals.get(goal.id), today).saved == usd("1000")


def test_accounts_in_groups(journey, monkeypatch):
    galicia = journey.account("Galicia", "100.000", group="Bancos")
    journey.account("Santander", "50.000", group="Bancos")
    journey.account("Billetera", "5.000")

    accounts = journey.show(PageId.ACCOUNTS)
    texts = journey.texts(accounts)
    assert "BANCOS" in [text.upper() for text in texts]
    assert any("150.000" in text for text in texts)  # the group's subtotal
    (group,) = journey.services.account_groups.list_groups()

    monkeypatch.setattr(confirm_dialog, "confirm", lambda *_args: True)
    accounts.delete_group(group)

    assert journey.services.account_groups.list_groups() == []
    assert journey.services.accounts.get(galicia.id).group_id is None
    assert "BANCOS" not in [text.upper() for text in journey.texts(accounts)]
    with journey.reopened() as again:
        assert len(again.accounts.list_accounts()) == 3


def test_a_copy_brings_the_data_back(journey, monkeypatch):
    today = date.today()
    banco = journey.account("Banco", "100.000")
    journey.spend(banco, "20.000", FOOD)
    settings = journey.show(PageId.SETTINGS)
    settings.data.backup_now_button.click()
    assert journey.toasts()[-1] == "Copia guardada."
    (copy,) = journey.paths.backups_dir.glob("nodus-*.db")
    monkeypatch.setattr(confirm_dialog, "confirm", lambda *_args: True)
    journey.show(PageId.ACCOUNTS)
    delete_account(
        journey.window, journey.services, journey.event_bus, journey.services.accounts.get(banco.id)
    )
    assert journey.services.accounts.list_accounts() == []

    monkeypatch.setattr(restore_copy.QFileDialog, "getOpenFileName", lambda *_a: (str(copy), ""))
    monkeypatch.setattr(restore_copy, "confirm", lambda *_a, **_k: True)
    journey.show(PageId.SETTINGS).data.restore_button.click()

    assert [a.name for a in journey.services.accounts.list_accounts()] == ["Banco"]
    assert journey.services.accounts.balance(banco.id) == ars("80000")
    assert "80.000,00" in " ".join(journey.texts(journey.window.sidebar))
    assert any(path.name.startswith("nodus-antes-de-restaurar") for path in
               journey.paths.backups_dir.iterdir())  # fmt: skip
    with journey.reopened() as again:
        assert again.accounts.balance(banco.id) == ars("80000")
        assert again.dashboard.summary(Period.of_months(Month.of(today))).expenses == ars("20000")
