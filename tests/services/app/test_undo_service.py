"""Undoing leaves the data exactly as it was before, or refuses and touches nothing."""

from datetime import date

import pytest
from factories import TODAY, ars, category_id, charge_draft, expense_draft, table_rows, usd

from nodus.models.bulk_changes import BulkChanges
from nodus.models.installment_plan import InstallmentPlan
from nodus.models.transaction import TransactionType
from nodus.services.app.undo_service import UndoError
from nodus.services.transactions.transfer_service import TransferDraft

CHARGE_TABLES = ("recurring_charges", "transactions")
PLAN_TABLES = ("installment_plans", "transactions")
NAME_TABLES = ("payees", "tags", "transaction_tags", "transactions")


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


class TestBulkEdit:
    def test_an_edit_is_undone_with_the_payee_and_tags_it_created(
        self, services, database, pesos, dollars
    ):
        first = services.transactions.create(
            expense_draft(services, pesos.id, ars("10"), tag_names=("Viaje",), note="Antes")
        )
        second = services.transactions.create(expense_draft(services, pesos.id, ars("20")))
        transfer = services.transfers.create(
            TransferDraft(pesos.id, dollars.id, ars("1200"), TODAY, amount_in=usd("1"))
        )
        before = table_rows(database, *NAME_TABLES)
        changes = BulkChanges(
            category_id=category_id(services, "Ocio", TransactionType.EXPENSE),
            payee_name="Coto",
            note="Compra",
            add_tags=("Vacaciones",),
            remove_tags=("Viaje",),
        )

        services.bulk_edits.apply([first.id, second.id, transfer.outgoing.id], changes)
        assert services.undo.last.description == "Se editaron 3 transacciones."
        services.undo.undo()

        assert table_rows(database, *NAME_TABLES) == before

    def test_one_transaction_is_said_in_singular(self, services, pesos):
        expense = services.transactions.create(expense_draft(services, pesos.id, ars("10")))

        services.bulk_edits.apply([expense.id], BulkChanges(note="Compra"))

        assert services.undo.last.description == "Se editó 1 transacción."

    def test_a_payee_it_created_and_used_since_stays(self, services, pesos):
        expense = services.transactions.create(expense_draft(services, pesos.id, ars("10")))
        services.bulk_edits.apply([expense.id], BulkChanges(payee_name="Coto"))
        services.transactions.create(
            expense_draft(services, pesos.id, ars("30"), payee_name="Coto")
        )

        services.undo.undo()

        assert services.transactions.get(expense.id).payee_id is None
        assert services.payees.find("Coto") is not None

    def test_a_transaction_edited_since_is_left_alone(self, services, database, pesos):
        expense = services.transactions.create(expense_draft(services, pesos.id, ars("10")))
        services.bulk_edits.apply([expense.id], BulkChanges(note="Compra"))
        services.transactions.update(
            expense.id, expense_draft(services, pesos.id, ars("15"), note="Otra")
        )
        edited = table_rows(database, *NAME_TABLES)

        with pytest.raises(UndoError, match="Alguna de esas transacciones cambió después"):
            services.undo.undo()

        assert table_rows(database, *NAME_TABLES) == edited


class TestMerge:
    def test_a_payee_merge_is_undone(self, services, database, pesos):
        groceries = category_id(services, "Supermercado y comida", TransactionType.EXPENSE)
        coto = services.payees.create("Coto")
        online = services.payees.create("Coto online", groceries)
        for name in ("Coto", "Coto online", "Coto online"):
            services.transactions.create(
                expense_draft(services, pesos.id, ars("10"), payee_name=name)
            )
        before = table_rows(database, *NAME_TABLES)

        services.payees.merge_many([online.id], coto.id)
        assert services.undo.last.description == "Se unieron 2 beneficiarios en Coto."
        services.undo.undo()

        assert table_rows(database, *NAME_TABLES) == before

    def test_a_payee_merge_is_not_undone_over_a_new_payee_with_the_name(
        self, services, database, pesos
    ):
        coto = services.payees.create("Coto")
        online = services.payees.create("Coto online")
        services.payees.merge_many([online.id], coto.id)
        services.payees.create("Coto Online")
        now = table_rows(database, *NAME_TABLES)

        with pytest.raises(UndoError, match="Ya hay otro beneficiario «Coto online»"):
            services.undo.undo()

        assert table_rows(database, *NAME_TABLES) == now

    def test_a_payee_renamed_since_is_left_alone(self, services):
        coto = services.payees.create("Coto")
        online = services.payees.create("Coto online")
        services.payees.merge_many([online.id], coto.id)
        services.payees.update(coto.id, "Supermercado Coto", None)

        with pytest.raises(UndoError, match="«Coto» cambió después"):
            services.undo.undo()

    def test_a_tag_merge_is_undone(self, services, database, pesos):
        for names in (("Viaje", "Vacaciones"), ("Viaje",), ("Paseo",), ("Vacaciones",)):
            services.transactions.create(
                expense_draft(services, pesos.id, ars("10"), tag_names=names)
            )
        viaje, vacaciones, paseo = (
            services.tags.find(name) for name in ("Viaje", "Vacaciones", "Paseo")
        )
        before = table_rows(database, *NAME_TABLES)

        services.tags.merge_many([viaje.id, paseo.id], vacaciones.id)
        assert services.undo.last.description == "Se unieron 3 etiquetas en Vacaciones."
        services.undo.undo()

        assert table_rows(database, *NAME_TABLES) == before

    def test_a_tag_merge_is_not_undone_over_a_new_tag_with_the_name(self, services, pesos):
        services.transactions.create(
            expense_draft(services, pesos.id, ars("10"), tag_names=("Viaje", "Paseo"))
        )
        viaje, paseo = (services.tags.find(name) for name in ("Viaje", "Paseo"))
        services.tags.merge_many([paseo.id], viaje.id)
        services.tags.create("paseo")

        with pytest.raises(UndoError, match="Ya hay otra etiqueta «Paseo»"):
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
