"""Undoing leaves the data exactly as it was before, or refuses and touches nothing."""

from datetime import date

import pytest
from factories import TODAY, ars, charge_draft, expense_draft, table_rows

from nodus.models.installment_plan import InstallmentPlan
from nodus.services.undo_service import UndoError

CHARGE_TABLES = ("recurring_charges", "transactions")
PLAN_TABLES = ("installment_plans", "transactions")


@pytest.fixture
def internet(services, pesos):
    return services.recurring.create(
        charge_draft(services, pesos.id, ars("15000"), date(2026, 10, 31), name="Internet")
    )


@pytest.fixture
def purchase(services, pesos):
    first = date(2026, 11, 10)
    draft = expense_draft(services, pesos.id, ars("75000"), first, note="Heladera")
    return services.installments.create(draft, InstallmentPlan(None, 6, ars("75000"), first))


class TestRecurring:
    def test_a_skip_is_undone(self, services, database, internet):
        before = table_rows(database, *CHARGE_TABLES)

        services.recurring.skip(internet.id)
        record = services.undo.last
        assert record.description == "Se omitió Internet."
        services.undo.undo()

        assert table_rows(database, *CHARGE_TABLES) == before
        assert services.undo.last is None

    def test_a_payment_is_undone_with_its_expense(self, services, database, pesos, internet):
        before = table_rows(database, *CHARGE_TABLES)

        services.recurring.pay(internet.id, ars("16200"), TODAY, pesos.id)
        assert services.undo.last.description == "Se pagó Internet."
        services.undo.undo()

        assert table_rows(database, *CHARGE_TABLES) == before

    def test_a_charge_edited_since_is_left_alone(self, services, database, pesos, internet):
        services.recurring.skip(internet.id)
        after = table_rows(database, *CHARGE_TABLES)
        services.recurring.update(
            internet.id, charge_draft(services, pesos.id, ars("20000"), date(2027, 1, 31))
        )
        edited = table_rows(database, *CHARGE_TABLES)

        with pytest.raises(UndoError, match="«Internet» cambió después"):
            services.undo.undo()

        assert table_rows(database, *CHARGE_TABLES) == edited != after

    def test_a_payment_edited_since_is_left_alone(self, services, database, pesos, internet):
        paid = services.recurring.pay(internet.id, ars("16200"), TODAY, pesos.id)
        services.transactions.update(
            paid.id, expense_draft(services, pesos.id, ars("17000"), TODAY, note="Internet")
        )

        with pytest.raises(UndoError, match="El pago de «Internet» cambió después"):
            services.undo.undo()

        assert services.transactions.get(paid.id).amount == ars("17000")


class TestInstallments:
    def test_paying_off_is_undone(self, services, database, purchase):
        before = table_rows(database, *PLAN_TABLES)

        services.installments.settle(purchase.id, date(2026, 12, 20))
        services.undo.undo()

        assert table_rows(database, *PLAN_TABLES) == before

    def test_a_purchase_unsettled_since_cannot_be_undone_again(self, services, purchase):
        services.installments.settle(purchase.id, date(2026, 12, 20))
        services.installments.unsettle(purchase.id)

        with pytest.raises(UndoError, match="La compra en cuotas cambió después"):
            services.undo.undo()


class TestService:
    def test_nothing_to_undo_says_so(self, services):
        with pytest.raises(UndoError, match="No hay nada para deshacer"):
            services.undo.undo()

    def test_the_same_action_is_undone_once(self, services, internet):
        services.recurring.skip(internet.id)
        record = services.undo.last
        services.undo.undo(record)

        with pytest.raises(UndoError, match="ya se deshizo"):
            services.undo.undo(record)

    def test_undoing_an_older_action_keeps_the_last(self, services, pesos, internet):
        services.recurring.skip(internet.id)
        older = services.undo.last
        other = services.recurring.create(
            charge_draft(services, pesos.id, ars("8500"), date(2026, 11, 20), name="Netflix")
        )
        services.recurring.skip(other.id)
        last = services.undo.last

        services.undo.undo(older)

        assert services.undo.last is last
