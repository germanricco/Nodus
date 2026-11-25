"""What a user can type into the forms, through the real widgets.

Every dialog is filled with text a person could type or paste and then saved. Saving must
either work or show a message; any other error fails the test, since pytest-qt turns an
exception raised inside a slot into a failure. Known defects are ``xfail(strict=True)`` with
their id in the v1.9 quality audit.
"""

from __future__ import annotations

from datetime import date

import pytest
from factories import TODAY, ars, category_id, charge_draft, expense_draft, light_theme, usd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLineEdit

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.models.money import MAX_CENTS, Money
from nodus.models.period import Month
from nodus.models.transaction import TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.transactions.transfer_service import TransferDraft
from nodus.ui.dialogs.account_dialog import AccountDialog
from nodus.ui.dialogs.account_group_dialogs import GroupDialog
from nodus.ui.dialogs.budget_dialog import BudgetDialog
from nodus.ui.dialogs.bulk_edit_dialog import BulkEditDialog
from nodus.ui.dialogs.category_dialog import CategoryDialog
from nodus.ui.dialogs.goal_dialog import GoalDialog
from nodus.ui.dialogs.payee_dialogs import PayeeDialog
from nodus.ui.dialogs.recurring_charge_dialog import PayChargeDialog, RecurringChargeDialog
from nodus.ui.dialogs.tag_dialogs import TagDialog
from nodus.ui.dialogs.transaction_dialog import INCOME_MODE, TransactionDialog
from nodus.ui.dialogs.value_adjustment_dialog import ValueAdjustmentDialog
from nodus.ui.navigation import PageId
from nodus.ui.shell.main_window import MainWindow
from nodus.ui.transaction_rows import TransactionListBuilder
from nodus.ui.widgets.inputs.amount_input import AmountInput
from nodus.ui.widgets.inputs.input_error import InputError

INCOME = TransactionType.INCOME


def known(reason: str):
    return pytest.mark.xfail(strict=True, reason=reason)


class TestAmountField:
    """The amount field reads what people type in Argentina, or says why it can't."""

    @pytest.mark.parametrize(
        "text,cents",
        [
            ("", 0),
            ("1500", 150000),
            ("1.500", 150000),
            ("1.500,50", 150050),
            ("12,5", 1250),
            ("12.50", 1250),
            (" 1 500 ", 150000),
            ("-5", -500),
        ],
    )
    def test_reads(self, qtbot, text, cents):
        assert self.read(qtbot, text) == Money(cents, Currency.ARS)

    @pytest.mark.parametrize(
        "text",
        [
            "abc",
            "+5",
            "1e5",
            "NaN",
            "Infinity",
            "∞",
            ",",
            ".",
            "-",
            "--5",
            "5-",
            "$100",
            "100$",
            "²",
        ],
    )
    def test_refuses_with_a_message(self, qtbot, text):
        with pytest.raises(InputError):
            self.read(qtbot, text)

    @pytest.mark.parametrize(
        "text",
        [
            "9" * 17,
            "9" * 30,
            "1,234.56",
            "10,005",
            "12.5.5",
            "1,234",
        ],
    )
    def test_refuses_what_it_would_have_to_guess(self, qtbot, text):
        with pytest.raises(InputError):
            self.read(qtbot, text)

    @pytest.mark.parametrize("text", ["1500,5", "0,4"])
    def test_chilean_pesos_have_no_cents(self, qtbot, text):
        with pytest.raises(InputError):
            self.read(qtbot, text, Currency.CLP)

    @staticmethod
    def read(qtbot, text: str, currency: Currency = Currency.ARS) -> Money:
        field = AmountInput(currency)
        qtbot.addWidget(field)
        field.line_edit.setText(text)
        return field.money()

    @pytest.mark.parametrize(
        ("text", "shown"),
        [
            ("1.500+2.300", "= $ 3.800,00"),
            ("36000/3", "= $ 12.000,00"),
            ("1500", None),  # a plain amount needs no result
            ("1500+", None),  # nothing while it is being typed
        ],
    )
    def test_a_calculation_shows_its_result_under_it(self, qtbot, text, shown):
        """The result is what is saved; the text stays as typed, so it can be fixed."""
        field = AmountInput(Currency.ARS)
        qtbot.addWidget(field)
        field.line_edit.setText(text)

        label = field.result_label
        assert (None if label.isHidden() else label.text()) == shown
        assert field.line_edit.text() == text


@pytest.fixture
def world(services, pesos):
    """One of each thing a dialog can edit: accounts, a movement, a charge."""
    savings = services.accounts.create("Ahorro", AccountType.SAVINGS, Currency.USD, usd("500"))
    investment = services.accounts.create(
        "Inversión", AccountType.INVESTMENT, Currency.ARS, ars("1000")
    )
    expense = services.transactions.create(expense_draft(services, pesos.id, ars("10")))
    charge = services.recurring.create(charge_draft(services, pesos.id, ars("100")))
    return {"savings": savings, "investment": investment, "expense": expense, "charge": charge}


DIALOGS = {
    "account": lambda s, b, t, w: AccountDialog(s, b),
    "category": lambda s, b, t, w: CategoryDialog(s, b),
    "payee": lambda s, b, t, w: PayeeDialog(s, b),
    "tag": lambda s, b, t, w: TagDialog(s, b),
    "group": lambda s, b, t, w: GroupDialog(s, b),
    "budget": lambda s, b, t, w: BudgetDialog(s, b, Month.of(TODAY)),
    "goal": lambda s, b, t, w: GoalDialog(s, b, today=TODAY),
    "charge": lambda s, b, t, w: RecurringChargeDialog(s, b),
    "pay charge": lambda s, b, t, w: PayChargeDialog(s, b, w["charge"], today=TODAY),
    "transaction": lambda s, b, t, w: TransactionDialog(s, b, t),
    "bulk edit": lambda s, b, t, w: BulkEditDialog(s, b, [w["expense"]]),
    "value": lambda s, b, t, w: ValueAdjustmentDialog(s, b, w["investment"], today=TODAY),
}

HOSTILE = {
    "blank": " ",
    "letters": "abc",
    "negative": "-5",
    "sql": "'; DROP TABLE transactions; --",
    "percent": "100%",
    "emoji": "emoji 💸",
    "long": "x" * 5000,
    "mixed separators": "1,234.56",
    "17 digits": "9" * 17,
    "30 digits": "9" * 30,
}

# Each (dialog, text) that fails today, with the finding that explains it.
KNOWN: dict[tuple[str, str], str] = {}


def cases() -> list:
    return [
        pytest.param(
            dialog,
            name,
            marks=[known(KNOWN[dialog, name])] if (dialog, name) in KNOWN else [],
            id=f"{dialog}-{name}",
        )
        for dialog in DIALOGS
        for name in HOSTILE
    ]


@pytest.mark.parametrize("dialog_name,text_name", cases())
def test_every_form_takes_any_text(
    qtbot, services, event_bus, theme_manager, world, dialog_name, text_name
):
    """Every text field gets the same text, as a hurried user might type, then «Guardar»."""
    dialog = DIALOGS[dialog_name](services, event_bus, theme_manager, world)
    qtbot.addWidget(dialog)
    for field in dialog.findChildren(QLineEdit):
        if not field.isReadOnly():
            field.setText(HOSTILE[text_name])
    dialog.save_button.click()
    services.transactions.list_transactions(TransactionFilter())  # the data is still readable


def test_goal_preview_with_a_target_that_is_not_a_number(qtbot, services, event_bus, world):
    dialog = GoalDialog(services, event_bus, today=TODAY)
    qtbot.addWidget(dialog)
    dialog.target_input.line_edit.setText("abc")


def test_nodus_opens_with_the_largest_amounts_saved(
    qtbot, services, event_bus, theme_manager, pesos
):
    services.settings.set_tour_offered(True)
    for _ in range(3):
        services.transactions.create(
            expense_draft(services, pesos.id, Money(MAX_CENTS, Currency.ARS))
        )
    window = MainWindow(services, event_bus, theme_manager)
    qtbot.addWidget(window)
    window.show()


def queries_to_build_rows(services, database, refunds: int) -> int:
    """How many statements the list runs to show ``refunds`` refunded expenses."""
    pesos = services.accounts.list_accounts()[0]
    for _ in range(refunds):
        expense = services.transactions.create(expense_draft(services, pesos.id, ars("100")))
        services.transactions.create(
            expense_draft(
                services,
                pesos.id,
                ars("10"),
                type=INCOME,
                category_id=category_id(services, "Reembolsos", INCOME),
                refund_of_id=expense.id,
                occurred_on=date(2026, 11, 6),
            )
        )
    rows = services.transactions.list_transactions(TransactionFilter())
    statements: list[str] = []
    database.connection.set_trace_callback(statements.append)
    try:
        TransactionListBuilder(services).build(rows)
    finally:
        database.connection.set_trace_callback(None)
    return len(statements)


def test_listing_more_refunds_does_not_take_more_queries(services, database, tmp_path, pesos):
    few = queries_to_build_rows(services, database, 2)
    more = queries_to_build_rows(services, database, 6)
    assert more == few


def test_a_renamed_refunds_category_still_links_refunds(
    qtbot, services, database, event_bus, pesos
):
    """Renamed before v1.9, when it still could be: the link follows its mark."""
    refunds = category_id(services, "Reembolsos", INCOME)
    with database.transaction():
        database.connection.execute(
            "UPDATE categories SET name = 'Devoluciones' WHERE id = ?", (refunds,)
        )
    dialog = TransactionDialog(services, event_bus, light_theme())
    qtbot.addWidget(dialog)
    dialog.mode_input.set_index(INCOME_MODE)
    dialog.category_input.select(refunds)
    dialog.category_input.activated.emit(dialog.category_input.currentIndex())
    assert dialog.form.isRowVisible(dialog.refund_input)


KEYS = [
    (Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier),  # nothing to undo yet
    (Qt.Key.Key_F1, Qt.KeyboardModifier.NoModifier),
    (Qt.Key.Key_F1, Qt.KeyboardModifier.NoModifier),  # and closed again
    (Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier),  # nothing selected
    (Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier),
    (Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier),
    (Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier),
]


@pytest.mark.parametrize("page_id", list(PageId), ids=lambda p: p.name.lower())
def test_keys_on_every_page_without_anything_to_act_on(qtbot, window, world, page_id):
    """Keys a user presses on a page where they have nothing to do: no error, no change."""
    window.show_page(page_id)
    before = window._services.transactions.list_transactions(TransactionFilter())
    for key, modifiers in KEYS:
        target = QApplication.focusWidget() or window
        qtbot.keyClick(target, key, modifiers)
    assert window._services.transactions.list_transactions(TransactionFilter()) == before


def queries_to_build_transfers(services, database, count: int, account_id: int) -> int:
    """How many statements the list of one account runs to show ``count`` transfers,
    whose other leg it does not have."""
    other = services.accounts.list_accounts()[-1]
    for _ in range(count):
        services.transfers.create(TransferDraft(account_id, other.id, ars("10"), TODAY))
    rows = services.transactions.list_transactions(TransactionFilter(account_id=account_id))
    statements: list[str] = []
    database.connection.set_trace_callback(statements.append)
    try:
        TransactionListBuilder(services).build(rows)
    finally:
        database.connection.set_trace_callback(None)
    return len(statements)


def test_listing_more_transfers_does_not_take_more_queries(services, database, pesos):
    services.accounts.create("Efectivo", AccountType.CASH, Currency.ARS, ars("0"))
    few = queries_to_build_transfers(services, database, 2, pesos.id)
    more = queries_to_build_transfers(services, database, 6, pesos.id)
    assert more == few
