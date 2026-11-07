from datetime import date
from decimal import Decimal

import pytest
from factories import TODAY, ars, category_id, charge_draft, eur, usd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.models.recurring_charge import Frequency
from nodus.models.transaction import TransactionType
from nodus.ui.dialogs.recurring_charge_dialog import PayChargeDialog, RecurringChargeDialog
from nodus.ui.labels import due_label
from nodus.ui.navigation import PageId
from nodus.ui.pages import recurring_page
from nodus.ui.pages.recurring_page import RecurringChargeRow, RecurringPage


@pytest.fixture
def page(qtbot, services, event_bus) -> RecurringPage:
    recurring = RecurringPage(services, event_bus)
    qtbot.addWidget(recurring)
    recurring.refresh(TODAY)
    return recurring


def create(services, account_id, amount="1000", due=TODAY, **overrides):
    return services.recurring.create(
        charge_draft(services, account_id, ars(amount), due, **overrides)
    )


def make(qtbot, dialog):
    qtbot.addWidget(dialog)
    return dialog


def click(qtbot, button):
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


@pytest.mark.parametrize(
    ("days", "text"),
    [(-3, "Vencido hace 3 días"), (-1, "Vencido ayer"), (0, "Hoy"), (1, "Mañana"),
     (5, "en 5 días")],
)  # fmt: skip
def test_due_label(days, text):
    assert due_label(days) == text


class TestChargeDialog:
    def test_creates_a_charge(self, qtbot, services, event_bus, pesos):
        dialog = make(qtbot, RecurringChargeDialog(services, event_bus))
        dialog.name_input.setText("Netflix")
        dialog.amount_input.line_edit.setText("8.500")
        dialog.category_input.select(category_id(services, "Ocio", TransactionType.EXPENSE))
        dialog.frequency_input.setCurrentIndex(dialog.frequency_input.findData(Frequency.ANNUAL))
        dialog.due_input.set_day(date(2026, 12, 1))

        with qtbot.waitSignal(event_bus.recurring_changed):
            click(qtbot, dialog.save_button)

        (charge,) = services.recurring.list_charges()
        assert (charge.name, charge.amount, charge.frequency) == (
            "Netflix",
            ars("8500"),
            Frequency.ANNUAL,
        )
        assert charge.account_id == pesos.id
        assert charge.next_due_on == date(2026, 12, 1)

    def test_amount_follows_the_account_currency(self, qtbot, services, event_bus, pesos, dollars):
        dialog = make(qtbot, RecurringChargeDialog(services, event_bus))

        dialog.account_input.select(dollars.id)

        dialog.amount_input.line_edit.setText("10")
        assert dialog.amount_input.money().currency.value == "USD"

    def test_amount_follows_an_account_in_euros(self, qtbot, services, event_bus, pesos):
        euros = services.accounts.create("Europa", AccountType.CASH, Currency.EUR, eur("0"))
        dialog = make(qtbot, RecurringChargeDialog(services, event_bus))

        dialog.account_input.select(euros.id)
        dialog.amount_input.line_edit.setText("10")

        assert dialog.amount_input.money() == eur("10")
        assert not dialog.form.isRowVisible(dialog.dollars_input)

    def test_edits_a_charge(self, qtbot, services, event_bus, pesos):
        charge = create(services, pesos.id)
        dialog = make(qtbot, RecurringChargeDialog(services, event_bus, charge))
        assert dialog.name_input.text() == "Internet"

        dialog.name_input.setText("Fibra óptica")
        click(qtbot, dialog.save_button)

        assert services.recurring.get(charge.id).name == "Fibra óptica"

    def test_shows_validation_errors(self, qtbot, services, event_bus, pesos):
        dialog = make(qtbot, RecurringChargeDialog(services, event_bus))
        dialog.amount_input.line_edit.setText("100")

        click(qtbot, dialog.save_button)

        assert "nombre" in dialog.error_label.text()
        assert services.recurring.list_charges() == []


class TestPayDialog:
    def test_comes_filled_in_and_records_the_payment(self, qtbot, services, event_bus, pesos):
        charge = create(services, pesos.id, "15000", date(2026, 11, 1))
        dialog = make(qtbot, PayChargeDialog(services, event_bus, charge, today=TODAY))
        assert dialog.amount_input.money() == ars("15000")
        assert dialog.date_input.day() == TODAY
        assert "01/12/2026" in dialog.next_hint.text()

        dialog.amount_input.line_edit.setText("16.000")
        with qtbot.waitSignals([event_bus.transactions_changed, event_bus.recurring_changed]):
            click(qtbot, dialog.save_button)

        assert services.accounts.balance(pesos.id) == ars("84000")
        assert services.recurring.get(charge.id).next_due_on == date(2026, 12, 1)


class TestPage:
    def test_empty_state(self, page):
        assert page.rows == []

    def test_groups_charges_by_when_they_are_due(self, qtbot, services, event_bus, pesos):
        create(services, pesos.id, due=date(2026, 11, 1), name="Vencido")
        create(services, pesos.id, due=date(2026, 11, 8), name="Pronto")
        create(services, pesos.id, due=date(2026, 12, 20), name="Después")
        paused = create(services, pesos.id, name="Pausado")
        services.recurring.set_active(paused.id, False)
        page = RecurringPage(services, event_bus)
        qtbot.addWidget(page)

        page.refresh(TODAY)

        assert [row.charge.name for row in page.rows] == ["Vencido", "Pronto", "Después", "Pausado"]
        overdue, *_rest, paused_row = page.rows
        assert overdue.status_label.text() == "Vencido hace 4 días"
        assert paused_row.pay_button is None
        assert page.active_label.text() == "3"
        assert page.monthly_label.text() == "$ 3.000,00"

    def test_nearest_charge_comes_first(self, qtbot, services, event_bus, pesos):
        """Created in any order, they list by date: within «Próximos 7 días» and after."""
        for day, name in [(date(2026, 11, 20), "Día 20"), (date(2026, 12, 2), "2 de dic"),
                          (date(2026, 11, 11), "Día 11"), (date(2026, 11, 8), "Día 8"),
                          (date(2026, 11, 30), "Día 30")]:  # fmt: skip
            create(services, pesos.id, due=day, name=name)
        page = RecurringPage(services, event_bus)
        qtbot.addWidget(page)

        page.refresh(date(2026, 11, 6))

        assert [row.charge.name for row in page.rows] == [
            "Día 8", "Día 11", "Día 20", "Día 30", "2 de dic"
        ]  # fmt: skip

    def test_skip_pause_and_delete(self, qtbot, services, event_bus, pesos, monkeypatch):
        charge = create(services, pesos.id)
        page = RecurringPage(services, event_bus)
        qtbot.addWidget(page)
        page.refresh(TODAY)

        click(qtbot, page.rows[0].skip_button)
        assert services.recurring.get(charge.id).next_due_on == date(2026, 12, 5)

        page.toggle_pause(services.recurring.get(charge.id))
        assert not services.recurring.get(charge.id).is_active

        monkeypatch.setattr(recurring_page, "confirm", lambda *_args: True)
        page.delete_charge(services.recurring.get(charge.id))
        assert services.recurring.list_charges() == []

    def test_row_menu_offers_resume_for_paused_charges(self, services, pesos):
        charge = create(services, pesos.id)
        services.recurring.set_active(charge.id, False)
        charge = services.recurring.get(charge.id)
        category = services.categories.get(charge.category_id)

        row = RecurringChargeRow(charge, category, "Banco", TODAY)

        assert [a.text() for a in row.menu.actions()] == ["Editar", "Reanudar", "Eliminar"]


def test_page_is_in_the_sidebar(window):
    window.show_page(PageId.RECURRING)

    assert isinstance(window.current_page, RecurringPage)


class TestDollarChargesPaidInPesos:
    @pytest.fixture
    def subscription(self, services, pesos):
        return services.recurring.create(
            charge_draft(services, pesos.id, usd("100"), TODAY, name="Suscripción")
        )

    def test_dollars_are_offered_only_for_peso_accounts(
        self, qtbot, services, event_bus, pesos, dollars
    ):
        dialog = make(qtbot, RecurringChargeDialog(services, event_bus))
        dialog.account_input.select(pesos.id)
        assert dialog.form.isRowVisible(dialog.dollars_input)

        dialog.dollars_input.setChecked(True)
        dialog.name_input.setText("Suscripción")
        dialog.amount_input.line_edit.setText("100")
        assert dialog.amount_input.money() == usd("100")
        dialog.account_input.select(dollars.id)
        assert not dialog.form.isRowVisible(dialog.dollars_input)
        dialog.account_input.select(pesos.id)
        click(qtbot, dialog.save_button)

        (charge,) = services.recurring.list_charges()
        assert (charge.amount, charge.account_id) == (usd("100"), pesos.id)

    def test_editing_keeps_the_box_checked(self, qtbot, services, event_bus, subscription):
        dialog = make(qtbot, RecurringChargeDialog(services, event_bus, subscription))

        assert dialog.dollars_input.isChecked()
        assert dialog.amount_input.money() == usd("100")

    def test_pay_asks_for_the_pesos_with_an_estimate(
        self, qtbot, services, event_bus, pesos, subscription
    ):
        services.exchange_rates.set_rate(TODAY, Decimal("1500"))
        dialog = make(qtbot, PayChargeDialog(services, event_bus, subscription, TODAY))

        assert dialog.charge_label.text() == "US$ 100,00"
        assert dialog.form.labelForField(dialog.amount_input).text() == "Pesos que salieron"
        assert dialog.amount_input.money() == ars("150000")
        assert "cotización guardada" in dialog.rate_hint.text()
        dialog.amount_input.line_edit.setText("165.000")
        click(qtbot, dialog.save_button)

        charge = services.recurring.get(subscription.id)
        again = make(qtbot, PayChargeDialog(services, event_bus, charge, TODAY))
        assert again.amount_input.money() == ars("165000")
        assert again.rate_hint.text() == "A $ 1.650,00 por dólar, como el último pago."

    def test_without_a_rate_the_pesos_start_empty(self, qtbot, services, event_bus, subscription):
        dialog = make(qtbot, PayChargeDialog(services, event_bus, subscription, TODAY))

        assert dialog.amount_input.line_edit.text() == ""
        assert "Sin cotización" in dialog.rate_hint.text()

    def test_page_shows_the_estimate(self, services, page, subscription):
        services.exchange_rates.set_rate(TODAY, Decimal("1500"))
        page.refresh(TODAY)

        (row,) = page.rows
        texts = [label.text() for label in row.findChildren(QLabel)]
        assert "US$ 100,00 ≈ $ 150.000,00" in texts
