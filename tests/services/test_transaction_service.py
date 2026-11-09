import dataclasses

import pytest
from factories import TODAY, ars, category_id, expense_draft, income_draft, usd

from nodus.models.account import AccountType
from nodus.models.bulk_changes import BulkChanges
from nodus.models.currency import Currency
from nodus.models.transaction import TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.errors import NotFoundError, ValidationError
from nodus.services.transaction_service import TransferDraft


class TestIncomeAndExpenses:
    def test_create_and_get(self, services, pesos):
        created = services.transactions.create(
            expense_draft(services, pesos.id, ars("1500"), note="  Verdulería ")
        )

        stored = services.transactions.get(created.id)
        assert stored.amount == ars("1500")
        assert stored.note == "Verdulería"
        assert stored.type is TransactionType.EXPENSE

    def test_category_must_match_type(self, services, pesos):
        sueldo = category_id(services, "Sueldo", TransactionType.INCOME)

        with pytest.raises(ValidationError, match="no corresponde"):
            services.transactions.create(
                expense_draft(services, pesos.id, ars("10"), category_id=sueldo)
            )

    def test_amount_must_be_in_account_currency(self, services, pesos):
        with pytest.raises(ValidationError, match="ARS"):
            services.transactions.create(expense_draft(services, pesos.id, usd("10")))

    def test_amount_must_be_positive(self, services, pesos):
        with pytest.raises(ValidationError, match="mayor que cero"):
            services.transactions.create(expense_draft(services, pesos.id, ars("0")))

    def test_archived_account_rejects_new_transactions(self, services, pesos):
        services.accounts.set_archived(pesos.id, True)

        with pytest.raises(ValidationError, match="archivada"):
            services.transactions.create(expense_draft(services, pesos.id, ars("10")))

    def test_missing_category_is_reported(self, services, pesos):
        with pytest.raises(NotFoundError):
            services.transactions.create(
                expense_draft(services, pesos.id, ars("10"), category_id=999)
            )

    def test_update_replaces_fields(self, services, pesos):
        created = services.transactions.create(expense_draft(services, pesos.id, ars("10")))

        services.transactions.update(
            created.id, income_draft(services, pesos.id, ars("99"), note="corregido")
        )

        updated = services.transactions.get(created.id)
        assert (updated.type, updated.amount, updated.note) == (
            TransactionType.INCOME, ars("99"), "corregido",
        )  # fmt: skip

    def test_delete(self, services, pesos):
        created = services.transactions.create(expense_draft(services, pesos.id, ars("10")))

        services.transactions.delete(created.id)

        with pytest.raises(NotFoundError):
            services.transactions.get(created.id)


class TestSeveralAtOnce:
    def test_delete_many_takes_transfers_whole(self, services, pesos, dollars):
        expense = services.transactions.create(expense_draft(services, pesos.id, ars("10")))
        kept = services.transactions.create(expense_draft(services, pesos.id, ars("20")))
        transfer = services.transactions.create_transfer(
            TransferDraft(pesos.id, dollars.id, ars("1200"), TODAY, amount_in=usd("1"))
        )

        services.transactions.delete_many([expense.id, transfer.outgoing.id, transfer.incoming.id])

        remaining = services.transactions.list_transactions(TransactionFilter())
        assert [t.id for t in remaining] == [kept.id]

    def test_delete_many_deletes_nothing_if_one_is_missing(self, services, pesos):
        expense = services.transactions.create(expense_draft(services, pesos.id, ars("10")))

        with pytest.raises(NotFoundError):
            services.transactions.delete_many([expense.id, 9999])

        assert services.transactions.get(expense.id).amount == ars("10")

    def test_bulk_edit_moves_them_all_to_a_category(self, services, pesos):
        ocio = category_id(services, "Ocio", TransactionType.EXPENSE)
        ids = [
            services.transactions.create(expense_draft(services, pesos.id, ars(a), note=a)).id
            for a in ("10", "20")
        ]

        services.transactions.bulk_edit(ids, BulkChanges(category_id=ocio))

        edited = [services.transactions.get(i) for i in ids]
        assert [t.category_id for t in edited] == [ocio, ocio]
        assert [t.note for t in edited] == ["10", "20"]  # what was left empty stays

    def test_bulk_edit_needs_a_category_that_suits_all(self, services, pesos):
        ocio = category_id(services, "Ocio", TransactionType.EXPENSE)
        expense = services.transactions.create(expense_draft(services, pesos.id, ars("10")))
        income = services.transactions.create(income_draft(services, pesos.id, ars("20")))

        with pytest.raises(ValidationError, match="no corresponde"):
            services.transactions.bulk_edit(
                [expense.id, income.id], BulkChanges(category_id=ocio, note="x")
            )

        assert services.transactions.get(expense.id).category_id != ocio
        assert services.transactions.get(expense.id).note == ""  # nothing changed

    def test_bulk_edit_needs_something_to_change(self, services, pesos):
        expense = services.transactions.create(expense_draft(services, pesos.id, ars("10")))

        with pytest.raises(ValidationError, match="al menos"):
            services.transactions.bulk_edit([expense.id], BulkChanges())

    def test_bulk_edit_sets_the_payee_and_the_note(self, services, pesos):
        ids = [
            services.transactions.create(expense_draft(services, pesos.id, ars(a))).id
            for a in ("10", "20")
        ]

        services.transactions.bulk_edit(ids, BulkChanges(payee_name="Coto", note="Compra"))

        coto = services.payees.find("Coto")
        assert {services.transactions.get(i).payee_id for i in ids} == {coto.id}
        assert {services.transactions.get(i).note for i in ids} == {"Compra"}

    def test_bulk_edit_adds_and_removes_tags_keeping_the_others(self, services, pesos):
        first = services.transactions.create(
            expense_draft(services, pesos.id, ars("10"), tag_names=("Viaje", "Trabajo"))
        )
        second = services.transactions.create(expense_draft(services, pesos.id, ars("20")))

        services.transactions.bulk_edit(
            [first.id, second.id], BulkChanges(add_tags=("Vacaciones",), remove_tags=("viaje",))
        )

        tags = services.transactions.tags_for([first.id, second.id])
        assert [t.name for t in tags[first.id]] == ["Trabajo", "Vacaciones"]
        assert [t.name for t in tags[second.id]] == ["Vacaciones"]

    def test_bulk_edit_gives_transfers_only_the_note(self, services, pesos, dollars):
        ocio = category_id(services, "Ocio", TransactionType.EXPENSE)
        expense = services.transactions.create(expense_draft(services, pesos.id, ars("10")))
        transfer = services.transactions.create_transfer(
            TransferDraft(pesos.id, dollars.id, ars("1200"), TODAY, amount_in=usd("1"))
        )

        services.transactions.bulk_edit(
            [expense.id, transfer.outgoing.id], BulkChanges(category_id=ocio, note="Viaje")
        )

        assert services.transactions.get(expense.id).category_id == ocio
        legs = services.transactions.get_transfer(transfer.outgoing.transfer_id)
        assert {legs.outgoing.note, legs.incoming.note} == {"Viaje"}
        assert legs.outgoing.category_id is None

    def test_bulk_edit_refuses_a_category_for_transfers_alone(self, services, pesos, dollars):
        ocio = category_id(services, "Ocio", TransactionType.EXPENSE)
        transfer = services.transactions.create_transfer(
            TransferDraft(pesos.id, dollars.id, ars("1200"), TODAY, amount_in=usd("1"))
        )

        with pytest.raises(ValidationError, match="transferencias"):
            services.transactions.bulk_edit([transfer.outgoing.id], BulkChanges(category_id=ocio))


class TestTransfers:
    def test_buying_dollars_moves_both_balances(self, services, pesos, dollars):
        transfer = services.transactions.create_transfer(
            TransferDraft(pesos.id, dollars.id, ars("120000"), TODAY, amount_in=usd("100"))
        )

        assert transfer.outgoing.type is TransactionType.EXPENSE
        assert transfer.incoming.type is TransactionType.INCOME
        assert transfer.outgoing.transfer_id == transfer.incoming.transfer_id == transfer.id
        assert services.accounts.balance(pesos.id) == ars("-20000")
        assert services.accounts.balance(dollars.id) == usd("600")

    def test_same_currency_defaults_incoming_to_outgoing(self, services, pesos):
        efectivo = services.accounts.create("Efectivo", AccountType.CASH, Currency.ARS, ars("0"))

        transfer = services.transactions.create_transfer(
            TransferDraft(pesos.id, efectivo.id, ars("5000"), TODAY)
        )

        assert transfer.incoming.amount == ars("5000")

    def test_same_currency_rejects_different_amounts(self, services, pesos):
        efectivo = services.accounts.create("Efectivo", AccountType.CASH, Currency.ARS, ars("0"))

        with pytest.raises(ValidationError, match="iguales"):
            services.transactions.create_transfer(
                TransferDraft(pesos.id, efectivo.id, ars("5000"), TODAY, amount_in=ars("4000"))
            )

    def test_different_currency_requires_incoming_amount(self, services, pesos, dollars):
        with pytest.raises(ValidationError, match="monto que entra"):
            services.transactions.create_transfer(
                TransferDraft(pesos.id, dollars.id, ars("120000"), TODAY)
            )

    def test_same_account_is_rejected(self, services, pesos):
        with pytest.raises(ValidationError, match="distintas"):
            services.transactions.create_transfer(
                TransferDraft(pesos.id, pesos.id, ars("1"), TODAY)
            )

    def test_update_rewrites_both_legs_keeping_ids(self, services, pesos, dollars):
        draft = TransferDraft(pesos.id, dollars.id, ars("120000"), TODAY, amount_in=usd("100"))
        original = services.transactions.create_transfer(draft)

        services.transactions.update_transfer(
            original.id, dataclasses.replace(draft, amount_out=ars("125000"), note="MEP")
        )

        updated = services.transactions.get_transfer(original.id)
        assert updated.outgoing.id == original.outgoing.id
        assert updated.incoming.id == original.incoming.id
        assert updated.outgoing.amount == ars("125000")
        assert updated.incoming.note == "MEP"

    def test_transfer_legs_cannot_be_edited_as_plain_transactions(self, services, pesos, dollars):
        transfer = services.transactions.create_transfer(
            TransferDraft(pesos.id, dollars.id, ars("120000"), TODAY, amount_in=usd("100"))
        )

        with pytest.raises(ValidationError):
            services.transactions.update(
                transfer.outgoing.id, expense_draft(services, pesos.id, ars("1"))
            )

    def test_deleting_one_leg_deletes_the_transfer(self, services, pesos, dollars):
        transfer = services.transactions.create_transfer(
            TransferDraft(pesos.id, dollars.id, ars("120000"), TODAY, amount_in=usd("100"))
        )

        services.transactions.delete(transfer.incoming.id)

        with pytest.raises(ValidationError):
            services.transactions.get_transfer(transfer.id)
        assert services.accounts.balance(pesos.id) == ars("100000")
        assert services.accounts.balance(dollars.id) == usd("500")
