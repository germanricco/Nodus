"""Linking refunds from the transaction dialog and seeing them in the transactions list."""

import pytest
from factories import (
    TODAY,
    ars,
    category_id,
    expense_draft,
    income_draft,
    light_theme,
    transaction_dialog,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.reports.export_service import HEADER
from nodus.ui.dialogs import confirm as confirm_dialog
from nodus.ui.dialogs.form_dialog import FIELD_ERROR
from nodus.ui.dialogs.refund_extra_dialog import RefundExtraDialog
from nodus.ui.dialogs.refund_picker import RefundPickerDialog
from nodus.ui.dialogs.transaction_dialog import EXPENSE_MODE, INCOME_MODE
from nodus.ui.pages.transactions_page import TransactionsPage
from nodus.ui.widgets.tables.transaction_table import (
    AMOUNT,
    BADGE,
    MOVEMENT,
    REFUND_MARK,
    SECOND_LINE_ROLE,
)

INCOME = TransactionType.INCOME


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


def choose_in_picker(monkeypatch, expense):
    """Makes the picker return ``expense`` as if the user chose it."""

    def fake_exec(picker):
        picker.chosen = expense
        return True

    monkeypatch.setattr(RefundPickerDialog, "exec", fake_exec)


def pick_category(dialog, category: int) -> None:
    """Chooses ``category`` as the user does, from the list."""
    dialog.category_input.select(category)
    dialog.category_input.activated.emit(dialog.category_input.currentIndex())


def test_refund_row_only_for_a_refund(qtbot, services, event_bus, pesos):
    dialog = transaction_dialog(qtbot, services, event_bus)

    assert not dialog.form.isRowVisible(dialog.refund_input)
    dialog.mode_input.set_index(INCOME_MODE)
    assert not dialog.form.isRowVisible(dialog.refund_input)  # an income, not yet a refund
    pick_category(dialog, category_id(services, "Reembolsos", INCOME))
    assert dialog.form.isRowVisible(dialog.refund_input)
    pick_category(dialog, category_id(services, "Sueldo", INCOME))
    assert not dialog.form.isRowVisible(dialog.refund_input)


def test_linking_a_refund_from_the_dialog(monkeypatch, qtbot, services, event_bus, pesos, shoes):
    choose_in_picker(monkeypatch, shoes)
    dialog = transaction_dialog(qtbot, services, event_bus)
    dialog.mode_input.set_index(INCOME_MODE)
    dialog.amount_input.line_edit.setText("400")
    pick_category(dialog, category_id(services, "Reembolsos", INCOME))

    dialog.refund_input.choose()

    assert "Zapatillas" in dialog.refund_input.summary_label.text()
    # Its figures on a line of their own, with no amount split between two lines.
    assert dialog.refund_input.detail_label.text().endswith("queda $ 1.000,00")
    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
    assert services.refunds.summary(shoes.id).refunded == ars("400")


def test_leaving_refunds_drops_the_link(monkeypatch, qtbot, services, event_bus, pesos, shoes):
    """A link the user can no longer see is never saved."""
    choose_in_picker(monkeypatch, shoes)
    dialog = transaction_dialog(qtbot, services, event_bus)
    dialog.mode_input.set_index(INCOME_MODE)
    dialog.amount_input.line_edit.setText("400")
    pick_category(dialog, category_id(services, "Reembolsos", INCOME))
    dialog.refund_input.choose()

    pick_category(dialog, category_id(services, "Sueldo", INCOME))
    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

    assert dialog.refund_input.expense_id() is None
    assert services.refunds.summary(shoes.id).refunded == ars("0")


def test_editing_keeps_or_removes_the_link(qtbot, services, event_bus, pesos, shoes):
    devolucion = refund(services, pesos, shoes)
    dialog = transaction_dialog(qtbot, services, event_bus, devolucion)

    assert dialog.refund_input.expense_id() == shoes.id
    assert dialog.refund_input.detail_label.text().endswith("queda $ 1.000,00")  # its own 400 aside
    qtbot.mouseClick(dialog.refund_input.unlink_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

    assert services.transactions.get(devolucion.id).refund_of_id is None


def test_edited_expense_shows_what_was_refunded(qtbot, services, event_bus, pesos, shoes):
    refund(services, pesos, shoes)
    dialog = transaction_dialog(qtbot, services, event_bus, shoes)

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
    assert "Elige" in picker.field_error(picker.table)

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
    return [model.index(row, MOVEMENT).data() for row in range(model.rowCount())]


def test_list_marks_both_sides_and_filters_them(services, pesos, shoes, page):
    refund(services, pesos, shoes)
    services.transactions.create(expense_draft(services, pesos.id, ars("10"), TODAY, note="Pan"))
    page.reload()

    assert sorted(descriptions(page)) == ["Devolución", "Pan", "Zapatillas"]
    model = page.model
    rows = {model.index(row, MOVEMENT).data(): row for row in range(model.rowCount())}
    # The refund shows its mark where the initial goes; the expense, what came back of it.
    assert model.index(rows["Devolución"], BADGE).data() == REFUND_MARK
    assert model.index(rows["Zapatillas"], BADGE).data() == "Z"
    assert model.index(rows["Zapatillas"], AMOUNT).data(SECOND_LINE_ROLE) == (
        "Reembolsado $ 400,00"
    )
    tooltip = model.index(rows["Devolución"], MOVEMENT).data(Qt.ItemDataRole.ToolTipRole)
    assert tooltip.startswith("Reembolso de «Zapatillas» del")

    page.type_filter.setCurrentText("Reembolsos")
    assert sorted(descriptions(page)) == ["Devolución", "Zapatillas"]


def test_deleting_a_refunded_expense_warns(monkeypatch, services, pesos, shoes, page):
    refund(services, pesos, shoes)
    page.reload()
    asked = []
    monkeypatch.setattr(confirm_dialog, "confirm", lambda _parent, _title, text: asked.append(text))
    row = descriptions(page).index("Zapatillas")

    page.table.selectRow(row)
    page.delete_selected()

    assert asked[0].endswith("Su reembolso queda como un ingreso común.")


def test_export_names_the_refunded_expense(services, pesos, shoes):
    devolucion = refund(services, pesos, shoes)

    rows = services.export.rows([devolucion])

    assert HEADER[-1] == "Reembolso de"
    assert rows[0][-1].endswith(" · Zapatillas")


class TestRefundWithExtra:
    """$ 1.000 back against a $ 1.000 purchase that already had $ 400 refunded."""

    def fill(self, monkeypatch, qtbot, services, event_bus, pesos, shoes, answer):
        refund(services, pesos, shoes)
        choose_in_picker(monkeypatch, shoes)
        monkeypatch.setattr(RefundExtraDialog, "exec", answer)
        dialog = transaction_dialog(qtbot, services, event_bus)
        dialog.mode_input.set_index(INCOME_MODE)
        dialog.amount_input.line_edit.setText("1000")
        pick_category(dialog, category_id(services, "Reembolsos", INCOME))
        dialog.refund_input.choose()
        dialog.save_button.click()
        return dialog

    def test_both_are_saved(self, monkeypatch, qtbot, services, event_bus, pesos, shoes):
        offered = []

        def accept(extra):
            offered.append(extra.category_input.currentText())
            extra.save_button.click()
            return extra.result()

        self.fill(monkeypatch, qtbot, services, event_bus, pesos, shoes, accept)

        assert offered == ["Otros"]
        assert services.refunds.summary(shoes.id).remaining == ars("0")
        others = category_id(services, "Otros", INCOME)
        incomes = [
            t for t in services.transactions.list_transactions(TransactionFilter())
            if t.category_id == others
        ]  # fmt: skip
        assert [t.amount for t in incomes] == [ars("400")]

    def test_cancel_keeps_the_form_open(
        self, monkeypatch, qtbot, services, event_bus, pesos, shoes
    ):
        dialog = self.fill(monkeypatch, qtbot, services, event_bus, pesos, shoes, lambda extra: 0)

        assert not dialog.result()
        assert "$ 600,00" in dialog.findChild(QLabel, FIELD_ERROR).text()
        assert len(services.refunds.summary(shoes.id).refunds) == 1


def visible_rows(dialog) -> list[str]:
    """The labels of the rows the form shows, top to bottom ("" for a line under a field)."""
    form = dialog.form
    rows = []
    for row in range(form.rowCount()):
        field = form.itemAt(row, form.ItemRole.FieldRole).widget()
        if form.isRowVisible(field):
            label = form.labelForField(field)
            rows.append(label.text() if label else "")
    return rows


def test_each_line_goes_under_the_field_it_follows(
    monkeypatch, qtbot, services, event_bus, pesos, shoes
):
    """The form is filled top to bottom: the expense a refund pays back right under the
    category that makes it one, and how much of an expense came back under its amount."""
    choose_in_picker(monkeypatch, shoes)
    dialog = transaction_dialog(qtbot, services, event_bus)
    dialog.mode_input.set_index(INCOME_MODE)
    pick_category(dialog, category_id(services, "Reembolsos", INCOME))
    rows = visible_rows(dialog)
    assert rows[rows.index("Categoría") + 1] == "Reembolso de"

    refund(services, pesos, shoes)
    edited = transaction_dialog(qtbot, services, event_bus, shoes)
    rows = visible_rows(edited)
    assert edited.refunded_hint.text().startswith("Reembolsado")
    assert rows[rows.index("Monto") + 1] == ""  # the line that says it
