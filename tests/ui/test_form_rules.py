"""The rules every form follows (principios-de-diseno: guía, realimentación, valores por
defecto), checked on all of them so a new form cannot skip them:

- each required field left empty says so in red under itself, all at once, with a red
  border and the focus on the first one; the foot of the dialog stays for the rest;
- a field's message goes away as soon as that field changes, and only that one;
- an error of a service's rule goes under the field it names;
- no list starts on a choice the user did not make.
"""

from collections.abc import Callable
from dataclasses import dataclass

import pytest
from factories import ars, category_id, charge_draft, expense_draft, light_theme
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLineEdit, QWidget

from nodus.models.period import Month
from nodus.models.transaction import TransactionType
from nodus.ui.dialogs.account_dialog import AccountDialog
from nodus.ui.dialogs.budget_dialog import BudgetDialog
from nodus.ui.dialogs.bulk_edit_dialog import BulkEditDialog
from nodus.ui.dialogs.category_dialog import CategoryDialog
from nodus.ui.dialogs.form_dialog import ERROR_PROPERTY, FormDialog
from nodus.ui.dialogs.payee_dialogs import PayeeDialog
from nodus.ui.dialogs.recurring_charge_dialog import PayChargeDialog, RecurringChargeDialog
from nodus.ui.dialogs.tag_dialogs import TagDialog
from nodus.ui.dialogs.transaction_dialog import (
    EXPENSE_MODE,
    INCOME_MODE,
    TRANSFER_MODE,
    TransactionDialog,
)
from nodus.ui.dialogs.value_adjustment_dialog import ValueAdjustmentDialog

EXPENSE = TransactionType.EXPENSE


def transaction_in(mode: int) -> Callable:
    def build(services, event_bus, accounts):
        dialog = TransactionDialog(services, event_bus, light_theme())
        dialog.mode_input.set_index(mode)
        return dialog

    return build


def pay_charge(services, event_bus, accounts):
    pesos, _dollars = accounts
    charge = services.recurring.create(charge_draft(services, pesos.id, ars("100")))
    return PayChargeDialog(services, event_bus, charge)


@dataclass
class Form:
    """A form, how to open it, and its required fields by attribute path."""

    name: str
    build: Callable
    required: tuple[str, ...]


FORMS = [
    Form(
        "gasto", transaction_in(EXPENSE_MODE), ("account_input", "amount_input", "category_input")
    ),
    Form(
        "ingreso", transaction_in(INCOME_MODE), ("account_input", "amount_input", "category_input")
    ),
    Form(
        "transferencia",
        transaction_in(TRANSFER_MODE),
        ("account_input", "to_account_input", "amount_input"),
    ),
    Form("cuenta", lambda s, e, a: AccountDialog(s, e), ("name_input",)),
    Form("categoría", lambda s, e, a: CategoryDialog(s, e), ("name_input",)),
    Form("beneficiario", lambda s, e, a: PayeeDialog(s, e), ("name_input",)),
    Form("etiqueta", lambda s, e, a: TagDialog(s, e), ("name_input",)),
    Form(
        "presupuesto",
        lambda s, e, a: BudgetDialog(s, e, Month(2026, 11)),
        ("category_input", "amount_input"),
    ),
    Form(
        "cargo recurrente",
        lambda s, e, a: RecurringChargeDialog(s, e),
        ("name_input", "amount_input", "account_input", "category_input"),
    ),
    Form("pago de un cargo", pay_charge, ("amount_input", "account_input")),
    Form(
        "ajuste de valor",
        lambda s, e, a: ValueAdjustmentDialog(s, e, a[1]),
        ("value_input",),
    ),
]


@pytest.fixture(params=FORMS, ids=[form.name for form in FORMS])
def form(request) -> Form:
    return request.param


@pytest.fixture
def opened(qtbot, services, event_bus, pesos, dollars, form) -> FormDialog:
    """The form, opened with every required field empty."""
    dialog = form.build(services, event_bus, (pesos, dollars))
    qtbot.addWidget(dialog)
    dialog.show()
    # Lists first: choosing an account may fill the amount in, as paying a charge does.
    fields = fields_of(dialog, form)
    for widget in sorted(fields, key=lambda w: not isinstance(input_of(w), QComboBox)):
        empty(widget)
    return dialog


def fields_of(dialog: FormDialog, form: Form) -> list[QWidget]:
    return [getattr(dialog, name) for name in form.required]


def input_of(widget: QWidget) -> QWidget:
    return getattr(widget, "line_edit", widget)


def empty(widget: QWidget) -> None:
    field = input_of(widget)
    if isinstance(field, QComboBox):
        field.setCurrentIndex(-1)
    elif isinstance(field, QLineEdit):
        field.clear()


def fill(widget: QWidget) -> None:
    field = input_of(widget)
    if isinstance(field, QComboBox):
        field.setCurrentIndex(0)
    elif isinstance(field, QLineEdit):
        field.setText("10")


def save(qtbot, dialog: FormDialog) -> None:
    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)


def test_every_missing_field_says_so_under_itself(qtbot, opened, form):
    save(qtbot, opened)

    fields = fields_of(opened, form)
    for widget in fields:
        assert opened.field_error(widget), f"«{form.name}»: no message under {widget}"
        assert input_of(widget).property(ERROR_PROPERTY) is True
    assert not opened.error_label.isVisibleTo(opened)
    assert opened.isVisible()  # nothing saved, nothing to retype
    qtbot.waitUntil(lambda: input_of(fields[0]).hasFocus())


def test_fixing_a_field_clears_only_its_message(qtbot, opened, form):
    save(qtbot, opened)
    first, *rest = fields_of(opened, form)

    fill(first)

    assert opened.field_error(first) is None
    assert not input_of(first).property(ERROR_PROPERTY)
    for widget in rest:
        assert opened.field_error(widget)


def test_a_new_form_chooses_nothing_for_the_user(qtbot, services, event_bus, pesos, dollars, form):
    """Lists of categories and destinations start empty; the account only with the last
    one used, or the only one there is."""
    dialog = form.build(services, event_bus, (pesos, dollars))
    qtbot.addWidget(dialog)

    for name in ("category_input", "to_account_input"):
        combo = getattr(dialog, name, None)
        if combo is not None and dialog._is_shown(combo):
            assert combo.current_id() is None, f"«{form.name}» starts with a {name}"


def test_the_only_account_is_offered(qtbot, services, event_bus, pesos):
    dialog = TransactionDialog(services, event_bus, light_theme())
    qtbot.addWidget(dialog)

    assert dialog.account_input.current_id() == pesos.id


class TestServiceRulesGoUnderTheirField:
    def test_a_zero_amount(self, qtbot, services, event_bus, pesos):
        dialog = TransactionDialog(services, event_bus, light_theme())
        qtbot.addWidget(dialog)
        dialog.amount_input.line_edit.setText("0")
        dialog.category_input.select(category_id(services, "Ocio", EXPENSE))

        save(qtbot, dialog)

        assert dialog.field_error(dialog.amount_input) == "El monto debe ser mayor que cero."

    def test_the_same_account_twice(self, qtbot, services, event_bus, pesos, dollars):
        dialog = TransactionDialog(services, event_bus, light_theme())
        qtbot.addWidget(dialog)
        dialog.mode_input.set_index(TRANSFER_MODE)
        dialog.account_input.select(pesos.id)
        dialog.to_account_input.select(pesos.id)
        dialog.amount_input.line_edit.setText("10")

        save(qtbot, dialog)

        assert "distintas" in dialog.field_error(dialog.to_account_input)

    def test_a_name_taken(self, qtbot, services, event_bus):
        dialog = CategoryDialog(services, event_bus)
        qtbot.addWidget(dialog)
        dialog.name_input.setText("Salud")

        save(qtbot, dialog)

        assert dialog.field_error(dialog.name_input) == "Ya existe una categoría con ese nombre."

    def test_a_rule_of_no_single_field_stays_at_the_foot(self, qtbot, services, event_bus, pesos):
        expense = services.transactions.create(expense_draft(services, pesos.id, ars("10")))
        dialog = BulkEditDialog(services, event_bus, [expense])
        qtbot.addWidget(dialog)

        save(qtbot, dialog)  # nothing filled in

        assert "al menos" in dialog.error_label.text()
        assert dialog.error_label.isVisibleTo(dialog)


def test_the_amount_has_the_focus_on_opening(qtbot, services, event_bus, pesos):
    dialog = TransactionDialog(services, event_bus, light_theme())
    qtbot.addWidget(dialog)
    dialog.show()

    qtbot.waitUntil(dialog.amount_input.line_edit.hasFocus)
