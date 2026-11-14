"""Empty lists offer the next step: create the first item, clear the filters or the search."""

import pytest
from factories import ars, expense_draft

from nodus.models.period import Month, Period
from nodus.ui import main_window
from nodus.ui.dialogs.transaction_dialog import TransactionDialog
from nodus.ui.navigation import DetailId, PageId
from nodus.ui.pages.accounts_page import AccountsPage
from nodus.ui.pages.payees_page import PayeesPage
from nodus.ui.pages.transactions_page import TransactionsPage
from nodus.ui.widgets.empty_state import EmptyState, empty_page_card


def test_no_accounts_offers_to_add_one(qtbot, services, event_bus, theme_manager, monkeypatch):
    page = AccountsPage(services, event_bus, theme_manager)
    qtbot.addWidget(page)
    opened = []
    monkeypatch.setattr(page, "open_account_dialog", lambda *args: opened.append(True))
    page.refresh()

    page.empty_create_button.click()

    assert opened == [True]


class TestTransactions:
    def make_page(self, qtbot, services, event_bus, theme_manager) -> TransactionsPage:
        page = TransactionsPage(services, event_bus, theme_manager)
        qtbot.addWidget(page)
        page.period_selector.set_period(Period.of_months(Month(2026, 11)))
        page.refresh()
        return page

    def test_an_empty_period_offers_to_add_one(self, qtbot, services, event_bus, theme_manager):
        page = self.make_page(qtbot, services, event_bus, theme_manager)
        asked = []
        page.new_transaction_requested.connect(lambda: asked.append(True))

        assert page.empty_state.text() == "Sin transacciones en este período."
        page.empty_state.action_button.click()
        assert asked == [True]

    def test_filters_that_leave_nothing_can_be_cleared(
        self, qtbot, services, event_bus, theme_manager, pesos
    ):
        services.transactions.create(expense_draft(services, pesos.id, ars("10")))
        page = self.make_page(qtbot, services, event_bus, theme_manager)
        page.search_input.setText("nada así")

        assert page.empty_state.action_button.text() == "Limpiar filtros"
        page.empty_state.action_button.click()

        assert page.search_input.text() == ""
        assert page.model.rowCount() == 1


class TestPayees:
    def make_page(self, qtbot, services, event_bus, theme_manager) -> PayeesPage:
        page = PayeesPage(services, event_bus, theme_manager)
        qtbot.addWidget(page)
        return page

    def test_none_yet_offers_to_add_one(
        self, qtbot, services, event_bus, theme_manager, monkeypatch
    ):
        page = self.make_page(qtbot, services, event_bus, theme_manager)
        created = []
        monkeypatch.setattr(page, "create_item", lambda: created.append(True))
        page.refresh()

        assert page.empty_state.action_button.text() == "Agregar beneficiario"
        page.empty_state.action_button.click()
        assert created == [True]

    def test_a_search_without_matches_can_be_cleared(
        self, qtbot, services, event_bus, theme_manager
    ):
        services.payees.create("Verdulería")
        page = self.make_page(qtbot, services, event_bus, theme_manager)
        page.refresh()
        page.search_input.setText("zzz")

        assert page.empty_state.action_button.text() == "Borrar búsqueda"
        page.empty_state.action_button.click()

        assert page.search_input.text() == ""
        assert page.model.rowCount() == 1


def test_a_page_with_nothing_yet_says_what_goes_there(qtbot):
    card, state = empty_page_card("Todavía no hay cuentas", "Una por cada lugar.", "Agregar", str)
    qtbot.addWidget(card)

    assert state.title.text() == "Todavía no hay cuentas"
    assert not state.title.isHidden()
    assert state.text() == "Una por cada lugar."
    assert state.action_button.objectName() == "PrimaryButton"


def test_a_compact_empty_state_keeps_to_its_message(qtbot):
    state = EmptyState("Sin cotizaciones.", compact=True)
    qtbot.addWidget(state)

    assert state.text() == "Sin cotizaciones."
    assert state.title.isHidden() and state.action_button.isHidden()
    assert state.label.property("compact") is True


def visible_empty_states(window) -> list[EmptyState]:
    """The empty states on screen that stand for a whole list, not a card's corner."""
    return [
        state
        for state in window.findChildren(EmptyState)
        if state.isVisible() and state.label.property("compact") is not True
    ]


@pytest.fixture
def opened(monkeypatch) -> list[TransactionDialog]:
    """The transaction forms opened, instead of shown."""
    forms = []
    monkeypatch.setattr(main_window.TransactionDialog, "exec", lambda self: forms.append(self))
    return forms


def test_every_empty_list_offers_a_way_out(window, services, pesos):
    payee = services.payees.create("Verdulería")
    tag = services.tags.create("Viaje")
    places = [lambda p=p: window.show_page(p) for p in PageId]
    places += [
        lambda: window.show_detail(DetailId.ACCOUNT, pesos.id),
        lambda: window.show_detail(DetailId.PAYEE, payee.id),
        lambda: window.show_detail(DetailId.TAG, tag.id),
    ]
    seen = []
    for show in places:
        show()
        for state in visible_empty_states(window):
            seen.append(state.text())
            assert state.action_button.isVisible(), state.text()
    # The sweep sees the lists it is about, or it would pass without looking.
    assert {
        "Sin transacciones en este período.",
        "Esta cuenta todavía no tiene movimientos.",
        "Todavía no tiene movimientos.",
    } <= set(seen)


def test_an_empty_account_adds_a_movement_to_itself(window, pesos, opened):
    window.show_detail(DetailId.ACCOUNT, pesos.id)
    detail = window._details[DetailId.ACCOUNT]

    detail.list_view.empty_state.action_button.click()

    assert opened[0].account_input.current_id() == pesos.id


def test_an_empty_payee_adds_a_movement_with_it(window, services, pesos, opened):
    payee = services.payees.create("Verdulería")
    window.show_detail(DetailId.PAYEE, payee.id)

    window._details[DetailId.PAYEE].list_view.empty_state.action_button.click()

    assert opened[0].payee_input.text() == "Verdulería"


def test_an_empty_tag_adds_a_movement_with_it(window, services, pesos, opened):
    tag = services.tags.create("Viaje")
    window.show_detail(DetailId.TAG, tag.id)

    window._details[DetailId.TAG].list_view.empty_state.action_button.click()

    assert opened[0].tag_input.names() == ("Viaje",)


def test_an_archived_account_offers_nothing(window, services, pesos):
    services.accounts.set_archived(pesos.id, True)
    window.show_detail(DetailId.ACCOUNT, pesos.id)

    assert window._details[DetailId.ACCOUNT].list_view.empty_state.action_button.isHidden()
