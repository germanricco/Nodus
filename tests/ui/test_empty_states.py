"""Empty lists offer the next step: create the first item, clear the filters or the search."""

from factories import ars, expense_draft

from nodus.models.period import Month, Period
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

    def test_an_empty_period_just_says_so(self, qtbot, services, event_bus, theme_manager):
        page = self.make_page(qtbot, services, event_bus, theme_manager)

        assert page.empty_state.text() == "Sin transacciones en este período."
        assert page.empty_state.action_button.isHidden()

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
