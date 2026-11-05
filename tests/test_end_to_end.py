"""The v0.1 scenario from start to finish, through the dialogs, over a file that is reopened."""

from datetime import date

from factories import ars, usd
from PySide6.QtWidgets import QLabel

from nodus.database.database import Database
from nodus.database.repositories.transaction_repository import TransactionFilter
from nodus.models.currency import Currency
from nodus.models.period import Month
from nodus.models.transaction import TransactionType
from nodus.services.container import Services
from nodus.ui.dialogs.account_dialog import AccountDialog
from nodus.ui.dialogs.transaction_dialog import (
    EXPENSE_MODE,
    INCOME_MODE,
    TRANSFER_MODE,
    TransactionDialog,
)
from nodus.ui.event_bus import EventBus
from nodus.ui.main_window import MainWindow
from nodus.ui.navigation import PageId
from nodus.ui.pages.settings_page import THEME_MODES
from nodus.ui.theme.theme import ThemeMode
from nodus.ui.theme.theme_manager import ThemeManager


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
    dialog = TransactionDialog(services, event_bus)
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
    services, event_bus = Services.create(database), EventBus()
    theme_manager = ThemeManager(qapp, ThemeMode.LIGHT)
    window = MainWindow(services, event_bus, theme_manager)
    qtbot.addWidget(window)

    banco = create_account(qtbot, services, event_bus, "Banco", Currency.ARS, "100.000")
    ahorro = create_account(qtbot, services, event_bus, "Ahorro", Currency.USD, "500")
    window.show_page(PageId.SETTINGS)
    settings = window.page(PageId.SETTINGS)
    settings.rate_value_input.line_edit.setText("1.200")
    settings.save_rate_button.click()
    record(qtbot, services, event_bus, INCOME_MODE, account=banco, amount="900.000",
           category="Sueldo")  # fmt: skip
    record(qtbot, services, event_bus, EXPENSE_MODE, account=banco, amount="85.000,50",
           category="Supermercado y comida")  # fmt: skip
    record(qtbot, services, event_bus, TRANSFER_MODE, account=banco, to_account=ahorro,
           amount="240.000", amount_in="200")  # fmt: skip
    settings.theme_input.set_index(THEME_MODES.index(ThemeMode.DARK))

    balances = services.accounts.balances()
    assert balances[banco.id] == ars("674999.50")
    assert balances[ahorro.id] == usd("700")
    summary = services.dashboard.month_summary(Month.of(today))
    assert (summary.income, summary.expenses) == (ars("900000"), ars("85000.50"))
    window.show_page(PageId.DASHBOARD)
    dashboard_texts = [label.text() for label in window.page(PageId.DASHBOARD).findChildren(QLabel)]
    assert "$ 814.999,50" in dashboard_texts  # the month's savings
    window.close()
    database.close()

    # Everything is still there after reopening the file.
    reopened = Database.open(tmp_path / "nodus.db")
    try:
        again = Services.create(reopened)
        assert again.accounts.balances() == balances
        assert again.net_worth.net_worth(today).total_in[Currency.ARS] == ars("1514999.50")
        assert again.settings.theme_preference() == "dark"
        legs = again.transactions.list_transactions(TransactionFilter(is_transfer=True))
        assert {leg.type for leg in legs} == {TransactionType.INCOME, TransactionType.EXPENSE}
    finally:
        reopened.close()
