"""The payees page and its dialogs."""

from datetime import date

import pytest
from factories import ars, category_id, expense_draft, income_draft
from menus import run_action, texts
from PySide6.QtCore import Qt

from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
from nodus.ui.dialogs.payee_dialogs import NO_DEFAULT_CATEGORY, MergePayeeDialog, PayeeDialog
from nodus.ui.navigation import TransactionFocus
from nodus.ui.pages import payees_page
from nodus.ui.pages.payees_page import NO_PAYEES_TEXT, PayeesPage
from nodus.ui.pages.summary_page import COUNT, NAME, TOTAL

EXPENSE = TransactionType.EXPENSE


@pytest.fixture
def page(qtbot, services, event_bus, theme_manager) -> PayeesPage:
    payees = PayeesPage(services, event_bus, theme_manager)
    qtbot.addWidget(payees)
    payees.show()
    payees.refresh()
    return payees


def column(page, index: int) -> list[str]:
    return [page.proxy.index(row, index).data() for row in range(page.proxy.rowCount())]


def select(page, name: str) -> None:
    row = column(page, NAME).index(name)
    page.table.selectRow(row)


@pytest.fixture
def populated(services, pesos):
    """Coto with three expenses, Empresa with one income and Kiosco without movements."""
    for day, amount in [(1, "100"), (3, "200"), (4, "50")]:
        services.transactions.create(
            expense_draft(services, pesos.id, ars(amount), date(2026, 10, day), payee_name="Coto")
        )
    services.transactions.create(
        income_draft(services, pesos.id, ars("1000"), date(2026, 11, 1), payee_name="Empresa")
    )
    services.payees.create("Kiosco")


def test_empty_state_explains_how_payees_appear(page):
    assert page.table.isHidden()
    assert page.empty_state.text() == NO_PAYEES_TEXT


def test_lists_most_used_first_with_totals(services, page, populated):
    page.refresh()

    assert column(page, NAME) == ["Coto", "Empresa", "Kiosco"]
    assert column(page, COUNT) == ["3", "1", "0"]
    assert column(page, TOTAL) == ["-$ 350,00", "$ 1.000,00", "—"]


def test_sorts_by_any_column(page, populated):
    page.refresh()

    page.table.sortByColumn(TOTAL, Qt.SortOrder.DescendingOrder)
    assert column(page, NAME)[0] == "Empresa"
    page.table.sortByColumn(NAME, Qt.SortOrder.AscendingOrder)
    assert column(page, NAME) == ["Coto", "Empresa", "Kiosco"]


def test_search_ignores_case_and_accents(services, page, populated):
    services.payees.create("Verdulería")
    page.refresh()

    page.search_input.setText("VERDULERIA")

    assert column(page, NAME) == ["Verdulería"]
    page.search_input.setText("zzz")
    assert page.table.isHidden()
    assert "búsqueda" in page.empty_state.text()


def actions_of(page, name: str):
    return page.row_actions(column(page, NAME).index(name))


def test_row_menu_offers_every_action(page, populated):
    page.refresh()

    actions = actions_of(page, "Kiosco")

    assert texts(actions) == ["Abrir", "Ver movimientos", "Editar", "Unir con…", "Eliminar"]
    assert [a.enabled for a in actions] == [True, False, True, True, True]  # no movements to show


def test_selection_bar_merges_and_deletes_several(
    monkeypatch, qtbot, services, event_bus, page, populated
):
    page.refresh()
    page.show()
    warnings = []
    monkeypatch.setattr(
        payees_page, "confirm", lambda _parent, _title, text: warnings.append(text) or True
    )
    select(page, "Coto")
    page.table.toggle_row(column(page, NAME).index("Empresa"))

    assert page.selection_bar.isVisible()
    assert page.selection_bar.count_label.text() == "2 seleccionados"
    assert not page.create_button.isVisible()
    with qtbot.waitSignal(event_bus.payees_changed):
        qtbot.keyClick(page.table, Qt.Key.Key_Delete)

    assert warnings == ["Se van a eliminar 2 beneficiarios. 4 movimientos quedan sin beneficiario."]
    assert column(page, NAME) == ["Kiosco"]


def test_see_transactions_spans_the_whole_history(qtbot, page, populated, services):
    page.refresh()

    with qtbot.waitSignal(page.transactions_requested) as signal:
        run_action(actions_of(page, "Coto"), "Ver movimientos")

    period = Period.of_months(Month(2026, 10), Month.of(date.today()))
    assert signal.args == [TransactionFocus(period, payee_id=services.payees.find("Coto").id)]


def test_delete_after_confirmation(monkeypatch, qtbot, services, event_bus, page, populated):
    page.refresh()
    warnings = []
    monkeypatch.setattr(
        payees_page, "confirm", lambda _parent, _title, text: warnings.append(text) or True
    )
    select(page, "Coto")

    with qtbot.waitSignal(event_bus.payees_changed):
        page.delete_button.click()

    assert warnings == ["Se va a eliminar «Coto». 3 movimientos quedan sin beneficiario."]
    assert column(page, NAME) == ["Empresa", "Kiosco"]


def test_delete_is_cancelled_when_not_confirmed(monkeypatch, page, services, populated):
    page.refresh()
    monkeypatch.setattr(payees_page, "confirm", lambda *_args: False)
    select(page, "Kiosco")

    page.delete_button.click()

    assert services.payees.find("Kiosco") is not None


def test_delete_key_deletes_the_selected_payee(monkeypatch, qtbot, services, page, populated):
    page.refresh()
    monkeypatch.setattr(payees_page, "confirm", lambda *_args: True)
    select(page, "Kiosco")

    qtbot.keyClick(page.table, Qt.Key.Key_Delete)

    assert services.payees.find("Kiosco") is None


class TestDialogs:
    def test_create_with_default_category(self, qtbot, services, event_bus, page):
        dialog = PayeeDialog(services, event_bus)
        qtbot.addWidget(dialog)
        assert dialog.category_input.currentText() == NO_DEFAULT_CATEGORY
        servicios = category_id(services, "Servicios", EXPENSE)
        dialog.name_input.setText("Edenor")
        dialog.category_input.select(servicios)

        with qtbot.waitSignal(event_bus.payees_changed):
            qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

        assert services.payees.find("edenor").default_category_id == servicios
        assert column(page, NAME) == ["Edenor"]

    def test_edit_rejects_a_duplicate_name(self, qtbot, services, event_bus):
        services.payees.create("Coto")
        dia = services.payees.create("Día")
        dialog = PayeeDialog(services, event_bus, dia)
        qtbot.addWidget(dialog)

        dialog.name_input.setText("coto")
        qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

        assert "Unir con" in dialog.error_label.text()

    def test_merge_explains_and_moves_transactions(self, qtbot, services, event_bus, populated):
        coto = services.payees.find("Coto")
        dialog = MergePayeeDialog(services, event_bus, [coto])
        qtbot.addWidget(dialog)
        dialog.target_input.setCurrentIndex(dialog.target_input.findText("Kiosco"))

        assert dialog.result_label.text() == (
            "Sus 3 movimientos pasan a «Kiosco» y «Coto» se elimina."
        )
        with qtbot.waitSignal(event_bus.transactions_changed):
            qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

        assert services.payees.find("Coto") is None
        assert services.payees.transaction_count(services.payees.find("Kiosco").id) == 3

    def test_merge_several_keeps_the_one_chosen(self, qtbot, services, event_bus, populated):
        payees = [services.payees.find(name) for name in ["Coto", "Empresa", "Kiosco"]]
        dialog = MergePayeeDialog(services, event_bus, payees)
        qtbot.addWidget(dialog)
        dialog.target_input.setCurrentIndex(dialog.target_input.findText("Kiosco"))

        assert dialog.windowTitle() == "Unir 3 beneficiarios"
        assert dialog.result_label.text() == (
            "4 movimientos pasan a «Kiosco» y se eliminan «Coto» y «Empresa»."
        )
        with qtbot.waitSignal(event_bus.transactions_changed):
            qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

        assert [p.name for p in services.payees.list_payees()] == ["Kiosco"]
