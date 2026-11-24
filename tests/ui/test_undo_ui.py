"""What changes data on one click is told in a toast with «Deshacer», which undoes it."""

from datetime import date

import pytest
from factories import ars, charge_draft, expense_draft
from menus import run_action
from PySide6.QtCore import Qt

from nodus.models.installment_plan import InstallmentPlan
from nodus.models.period import Month, Period
from nodus.models.transaction_filter import TransactionFilter
from nodus.ui.dialogs.bulk_edit_dialog import BulkEditDialog
from nodus.ui.dialogs.payee_dialogs import MergePayeeDialog
from nodus.ui.dialogs.recurring_charge_dialog import PayChargeDialog
from nodus.ui.dialogs.tag_dialogs import MergeTagDialog
from nodus.ui.navigation import PageId
from nodus.ui.widgets.tables.transaction_table import MOVEMENT


@pytest.fixture
def internet(services, pesos):
    return services.recurring.create(
        charge_draft(services, pesos.id, ars("15000"), date.today(), name="Internet")
    )


def toast_texts(window) -> list[str]:
    return [toast.text for toast in window.toasts.toasts]


def click_undo(window) -> None:
    window.toasts.toasts[-1].action_button.click()


def skip_on_recurrentes(window) -> None:
    window.show_page(PageId.RECURRING)
    run_action(window.page(PageId.RECURRING).rows[0].actions(), "Omitir")


def test_a_skip_offers_to_undo_it(services, window, internet):
    skip_on_recurrentes(window)

    assert toast_texts(window) == ["Se omitió Internet."]
    assert window.toasts.toasts[0].action_button.text() == "Deshacer"
    click_undo(window)

    assert services.recurring.get(internet.id).next_due_on == date.today()
    assert window.page(PageId.RECURRING).rows[0].charge.next_due_on == date.today()
    assert toast_texts(window) == ["Se deshizo."]


def test_a_payment_offers_to_undo_it(qtbot, services, window, pesos, internet):
    dialog = PayChargeDialog(services, window._event_bus, internet, parent=window)
    qtbot.addWidget(dialog)
    dialog.save_button.click()
    assert len(services.transactions.list_transactions(TransactionFilter())) == 1

    assert toast_texts(window) == ["Se pagó Internet."]
    click_undo(window)

    assert services.transactions.list_transactions(TransactionFilter()) == []
    assert services.recurring.get(internet.id).next_due_on == date.today()


def test_what_changed_since_is_not_undone_and_says_why(services, window, pesos, internet):
    skip_on_recurrentes(window)
    services.recurring.update(
        internet.id, charge_draft(services, pesos.id, ars("20000"), date(2027, 3, 10))
    )

    click_undo(window)

    assert services.recurring.get(internet.id).amount == ars("20000")
    assert toast_texts(window) == ["«Internet» cambió después, así que ya no se puede deshacer."]


def test_paying_off_installments_offers_to_undo_it(services, window, pesos):
    first = date.today()
    draft = expense_draft(services, pesos.id, ars("60000"), first, note="Heladera")
    purchase = services.installments.create(draft, InstallmentPlan(None, 6, ars("60000"), first))
    window.show_page(PageId.TRANSACTIONS)
    page = window.page(PageId.TRANSACTIONS)
    month = Month.of(first)
    page.period_selector.set_period(Period.of_months(month, month.shifted(6)))
    page.refresh()
    model = page.model
    row = next(
        i for i in range(model.rowCount()) if model.data(model.index(i, MOVEMENT)).endswith("2/6")
    )

    run_action(page.list_view.row_actions(row), "Adelantar las cuotas que faltan")
    assert toast_texts(window) == ["Se adelantaron las cuotas que faltaban."]
    click_undo(window)

    assert services.installments.plan(purchase.id).settled_on is None


def test_a_bulk_edit_offers_to_undo_it(qtbot, services, window, pesos):
    expenses = [
        services.transactions.create(expense_draft(services, pesos.id, ars(a), note=a))
        for a in ("10", "20")
    ]
    dialog = BulkEditDialog(services, window._event_bus, expenses, parent=window)
    qtbot.addWidget(dialog)
    dialog.payee_input.line_edit.setText("Coto")
    dialog.save_button.click()

    assert toast_texts(window) == ["Se editaron 2 transacciones."]
    click_undo(window)

    assert {services.transactions.get(t.id).payee_id for t in expenses} == {None}
    assert services.payees.find("Coto") is None


def test_merging_payees_offers_to_undo_it(qtbot, services, window, pesos):
    for name in ("Coto", "Coto online"):
        services.transactions.create(expense_draft(services, pesos.id, ars("10"), payee_name=name))
    online = services.payees.find("Coto online")
    dialog = MergePayeeDialog(services, window._event_bus, [online], parent=window)
    qtbot.addWidget(dialog)
    dialog.target_input.setCurrentIndex(dialog.target_input.findText("Coto"))
    dialog.save_button.click()

    assert toast_texts(window) == ["Se unieron 2 beneficiarios en Coto."]
    click_undo(window)

    assert services.payees.transaction_count(online.id) == 1


def test_merging_tags_offers_to_undo_it(qtbot, services, window, pesos):
    services.transactions.create(
        expense_draft(services, pesos.id, ars("10"), tag_names=("Viaje", "Paseo"))
    )
    paseo = services.tags.find("Paseo")
    dialog = MergeTagDialog(services, window._event_bus, [paseo], parent=window)
    qtbot.addWidget(dialog)
    dialog.target_input.setCurrentIndex(dialog.target_input.findText("Viaje"))
    dialog.save_button.click()

    assert toast_texts(window) == ["Se unieron 2 etiquetas en Viaje."]
    click_undo(window)

    assert services.tags.transaction_count(paseo.id) == 1


def test_ctrl_z_undoes_the_last_action(qtbot, services, window, internet):
    skip_on_recurrentes(window)
    window.activateWindow()
    qtbot.waitUntil(window.isActiveWindow)

    qtbot.keyClick(window, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)

    assert services.recurring.get(internet.id).next_due_on == date.today()
    assert toast_texts(window)[-1] == "Se deshizo."


def test_ctrl_z_with_nothing_to_undo_says_so(window):
    window.undo_last()

    assert toast_texts(window) == ["No hay nada para deshacer."]
