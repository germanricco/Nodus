"""What changes data on one click is told in a toast with «Deshacer», which undoes it."""

from datetime import date

import pytest
from factories import ars, charge_draft, expense_draft
from menus import run_action

from nodus.models.installment_plan import InstallmentPlan
from nodus.models.period import Month, Period
from nodus.models.transaction_filter import TransactionFilter
from nodus.ui.dialogs.recurring_charge_dialog import PayChargeDialog
from nodus.ui.navigation import PageId
from nodus.ui.widgets.transaction_table import DESCRIPTION


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
        i
        for i in range(model.rowCount())
        if model.data(model.index(i, DESCRIPTION)).endswith("2/6")
    )

    run_action(page.list_view.row_actions(row), "Adelantar las cuotas que faltan")
    assert toast_texts(window) == ["Se adelantaron las cuotas que faltaban."]
    click_undo(window)

    assert services.installments.plan(purchase.id).settled_on is None
