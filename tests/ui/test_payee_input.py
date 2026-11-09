"""The payee field of the transaction dialog."""

from factories import ars, category_id, expense_draft, light_theme
from PySide6.QtCore import Qt

from nodus.models.transaction import TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.ui.dialogs.transaction_dialog import INCOME_MODE, TRANSFER_MODE, TransactionDialog

EXPENSE = TransactionType.EXPENSE


def make_dialog(qtbot, services, event_bus, transaction=None) -> TransactionDialog:
    dialog = TransactionDialog(services, event_bus, light_theme(), transaction)
    qtbot.addWidget(dialog)
    return dialog


def type_payee(qtbot, dialog, text: str) -> None:
    qtbot.keyClicks(dialog.payee_input.line_edit, text)


def choose_payee(qtbot, dialog, text: str) -> None:
    """Types ``text`` and leaves the field, as when picking a suggestion."""
    type_payee(qtbot, dialog, text)
    dialog.payee_input.line_edit.editingFinished.emit()


def test_typing_suggests_matching_payees_ignoring_accents(qtbot, services, event_bus, pesos):
    for name in ["Verdulería", "La verdura", "Coto"]:
        services.payees.create(name)
    dialog = make_dialog(qtbot, services, event_bus)

    type_payee(qtbot, dialog, "verd")

    assert dialog.payee_input.names.suggestions.stringList() == ["Verdulería", "La verdura"]
    assert dialog.payee_input.hint.text() == "Se creará «verd»"


def test_choosing_a_payee_fills_in_its_category(qtbot, services, event_bus, pesos):
    servicios = category_id(services, "Servicios", EXPENSE)
    services.payees.create("Edenor", servicios)
    dialog = make_dialog(qtbot, services, event_bus)

    choose_payee(qtbot, dialog, "edenor")

    assert dialog.category_input.current_id() == servicios


def test_a_category_picked_by_hand_is_kept(qtbot, services, event_bus, pesos):
    services.payees.create("Edenor", category_id(services, "Servicios", EXPENSE))
    salud = category_id(services, "Salud", EXPENSE)
    dialog = make_dialog(qtbot, services, event_bus)
    dialog.category_input.select(salud)
    dialog.category_input.activated.emit(dialog.category_input.currentIndex())

    choose_payee(qtbot, dialog, "Edenor")

    assert dialog.category_input.current_id() == salud


def test_new_name_shows_hint_and_is_created_on_saving(qtbot, services, event_bus, pesos):
    dialog = make_dialog(qtbot, services, event_bus)
    dialog.amount_input.line_edit.setText("100")

    # QTest.keyClicks crashes on accented letters, so the name is set as a paste would.
    dialog.payee_input.line_edit.setText("Verdulería Don José")

    assert not dialog.payee_input.hint.isHidden()
    assert dialog.payee_input.hint.text() == "Se creará «Verdulería Don José»"
    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
    payee = services.payees.find("verduleria don jose")
    (transaction,) = services.transactions.list_transactions(TransactionFilter(payee_id=payee.id))
    assert transaction.amount == ars("100")


def test_payee_row_is_hidden_for_transfers(qtbot, services, event_bus, pesos):
    dialog = make_dialog(qtbot, services, event_bus)

    dialog.mode_input.set_index(TRANSFER_MODE)
    assert not dialog.form.isRowVisible(dialog.payee_input)

    dialog.mode_input.set_index(INCOME_MODE)
    assert dialog.form.isRowVisible(dialog.payee_input)


def test_editing_shows_the_current_payee_and_keeps_the_category(qtbot, services, event_bus, pesos):
    services.payees.create("Coto", category_id(services, "Servicios", EXPENSE))
    created = services.transactions.create(
        expense_draft(services, pesos.id, ars("10"), payee_name="Coto")
    )
    dialog = make_dialog(qtbot, services, event_bus, services.transactions.get(created.id))

    assert dialog.payee_input.text() == "Coto"
    assert dialog.category_input.current_id() == created.category_id
