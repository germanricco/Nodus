"""Linking refunds from the transaction dialog and seeing them in the transactions list."""

from datetime import date

import pytest
from factories import ars, category_id, expense_draft, income_draft, light_theme
from PySide6.QtCore import Qt

from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
from nodus.services.export_service import HEADER
from nodus.ui.dialogs.refund_picker import RefundPickerDialog
from nodus.ui.dialogs.transaction_dialog import EXPENSE_MODE, INCOME_MODE, TransactionDialog
from nodus.ui.pages import transaction_list_view
from nodus.ui.pages.transactions_page import TransactionsPage
from nodus.ui.widgets.transaction_table import DESCRIPTION

INCOME = TransactionType.INCOME
TODAY = date.today()


@pytest.fixture
def shoes(services, pesos):
    """A $ 1.000 purchase this month."""
    return services.transactions.create(
        expense_draft(services, pesos.id, ars("1000"), TODAY, note="Zapatillas")
    )


def refund(services, pesos, expense, amount="400"):
    return services.transactions.create(
        income_draft(
            services, pesos.id, ars(amount), TODAY, note="Devolución",
            category_id=category_id(services, "Reembolsos", INCOME), refund_of_id=expense.id,
        )
    )  # fmt: skip


def make_dialog(qtbot, services, event_bus, transaction=None) -> TransactionDialog:
    dialog = TransactionDialog(services, event_bus, light_theme(), transaction)
    qtbot.addWidget(dialog)
    return dialog


def choose_in_picker(monkeypatch, expense):
    """Makes the picker return ``expense`` as if the user chose it."""

    def fake_exec(picker):
        picker.chosen = expense
        return True

    monkeypatch.setattr(RefundPickerDialog, "exec", fake_exec)


def test_refund_row_only_for_income(qtbot, services, event_bus, pesos):
    dialog = make_dialog(qtbot, services, event_bus)

    assert not dialog.form.isRowVisible(dialog.refund_input)
    dialog.mode_input.set_index(INCOME_MODE)
    assert dialog.form.isRowVisible(dialog.refund_input)


def test_linking_a_refund_from_the_dialog(monkeypatch, qtbot, services, event_bus, pesos, shoes):
    choose_in_picker(monkeypatch, shoes)
    dialog = make_dialog(qtbot, services, event_bus)
    dialog.mode_input.set_index(INCOME_MODE)
    dialog.amount_input.line_edit.setText("400")

    dialog.refund_input.choose()

    assert "Zapatillas" in dialog.refund_input.summary_label.text()
    assert "queda $ 1.000,00" in dialog.refund_input.summary_label.text()
    assert dialog.category_input.current_id() == category_id(services, "Reembolsos", INCOME)
    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
    assert services.transactions.refund_summary(shoes.id).refunded == ars("400")


def test_editing_keeps_or_removes_the_link(qtbot, services, event_bus, pesos, shoes):
    devolucion = refund(services, pesos, shoes)
    dialog = make_dialog(qtbot, services, event_bus, devolucion)

    assert dialog.refund_input.expense_id() == shoes.id
    assert "queda $ 1.000,00" in dialog.refund_input.summary_label.text()  # its own 400 aside
    qtbot.mouseClick(dialog.refund_input.unlink_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

    assert services.transactions.get(devolucion.id).refund_of_id is None


def test_edited_expense_shows_what_was_refunded(qtbot, services, event_bus, pesos, shoes):
    refund(services, pesos, shoes)
    dialog = make_dialog(qtbot, services, event_bus, shoes)

    assert dialog.mode_input.index() == EXPENSE_MODE
    assert dialog.refunded_hint.text() == "Reembolsado $ 400,00 de $ 1.000,00"
    assert dialog.form.isRowVisible(dialog.refunded_hint)


def test_picker_leaves_out_fully_refunded_expenses(qtbot, services, pesos, shoes):
    other = services.transactions.create(
        expense_draft(services, pesos.id, ars("50"), TODAY, note="Kiosco")
    )
    refund(services, pesos, other, "50")

    picker = RefundPickerDialog(services, light_theme())
    qtbot.addWidget(picker)
    shown = [picker.model.item(row).transaction.id for row in range(picker.model.rowCount())]
    assert shown == [shoes.id]

    picker.search_input.setText("kiosco")
    assert picker.model.rowCount() == 0
    assert not picker.empty_label.isHidden()


def test_picker_requires_a_choice(qtbot, services, pesos, shoes):
    picker = RefundPickerDialog(services, light_theme())
    qtbot.addWidget(picker)

    qtbot.mouseClick(picker.save_button, Qt.MouseButton.LeftButton)
    assert "Elige" in picker.error_label.text()

    picker.table.selectRow(0)
    qtbot.mouseClick(picker.save_button, Qt.MouseButton.LeftButton)
    assert picker.chosen == shoes


@pytest.fixture
def page(qtbot, services, event_bus, theme_manager) -> TransactionsPage:
    transactions = TransactionsPage(services, event_bus, theme_manager)
    qtbot.addWidget(transactions)
    transactions.period_selector.set_period(Period.of_months(Month.of(TODAY)))
    transactions.refresh()
    return transactions


def descriptions(page) -> list[str]:
    model = page.model
    return [model.index(row, DESCRIPTION).data() for row in range(model.rowCount())]


def test_list_marks_both_sides_and_filters_them(services, pesos, shoes, page):
    refund(services, pesos, shoes)
    services.transactions.create(expense_draft(services, pesos.id, ars("10"), TODAY, note="Pan"))
    page.reload()

    assert sorted(descriptions(page)) == ["Pan", "↺ Devolución", "↺ Zapatillas"]
    tooltips = {
        page.model.index(row, DESCRIPTION).data(): page.model.index(row, DESCRIPTION).data(
            Qt.ItemDataRole.ToolTipRole
        )
        for row in range(page.model.rowCount())
    }
    assert tooltips["↺ Zapatillas"] == "Reembolsado $ 400,00"
    assert tooltips["↺ Devolución"].startswith("Reembolso de «Zapatillas» del")

    page.type_filter.setCurrentText("Reembolsos")
    assert sorted(descriptions(page)) == ["↺ Devolución", "↺ Zapatillas"]


def test_deleting_a_refunded_expense_warns(monkeypatch, services, pesos, shoes, page):
    refund(services, pesos, shoes)
    page.reload()
    asked = []
    monkeypatch.setattr(
        transaction_list_view, "confirm", lambda _parent, _title, text: asked.append(text)
    )
    row = descriptions(page).index("↺ Zapatillas")

    page.table.selectRow(row)
    page.delete_selected()

    assert asked[0].endswith("Su reembolso queda como un ingreso común.")


def test_export_names_the_refunded_expense(services, pesos, shoes):
    devolucion = refund(services, pesos, shoes)

    rows = services.export.rows([devolucion])

    assert HEADER[-1] == "Reembolso de"
    assert rows[0][-1].endswith(" · Zapatillas")
