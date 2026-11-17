"""Changing several movements at once, with its «Deshacer»."""

from __future__ import annotations

import dataclasses

from nodus.database.database import Database
from nodus.database.repositories.category_repository import CategoryRepository
from nodus.database.repositories.payee_repository import PayeeRepository
from nodus.database.repositories.tag_repository import TagRepository
from nodus.database.repositories.transaction_repository import TransactionRepository
from nodus.models.bulk_changes import BulkChanges
from nodus.models.transaction import Transaction
from nodus.services.app.undo_service import UndoService, changed_since
from nodus.services.errors import ValidationError, require_found
from nodus.services.transactions.labels import MovementLabels


class BulkEditService:
    def __init__(
        self,
        database: Database,
        transactions: TransactionRepository,
        categories: CategoryRepository,
        payees: PayeeRepository,
        tags: TagRepository,
        labels: MovementLabels,
        undo: UndoService,
    ) -> None:
        self._database = database
        self._transactions = transactions
        self._categories = categories
        self._payees = payees
        self._tags = tags
        self._labels = labels
        self._undo = undo

    def apply(self, transaction_ids: list[int], changes: BulkChanges) -> None:
        """Applies ``changes`` to every one of ``transaction_ids``, or to none if one fails.

        Transfers take only the note, on both legs: they have no category, payee or tags.
        A new category must suit every expense or income chosen. It can be undone.
        """
        if changes.is_empty:
            raise ValidationError("Completa al menos un campo para cambiar.")
        transactions = [self._get(transaction_id) for transaction_id in transaction_ids]
        movements = [t for t in transactions if not t.is_transfer]
        if changes.category_id is not None:
            self._require_category_for(changes.category_id, movements)
        note = changes.note.strip()
        transfer_ids = {t.transfer_id for t in transactions if t.is_transfer}
        legs = [
            leg
            for transfer_id in (transfer_ids if note else ())
            for leg in self._transactions.list_transfer_legs(transfer_id)
        ]
        before = movements + legs
        tags_before = self._labels.tag_ids_of(movements)
        payees_before = {payee.id for payee in self._payees.list()}
        tags_known = {tag.id for tag in self._tags.list()}
        with self._database.transaction():
            for transaction in movements:
                edited = transaction
                if changes.category_id is not None:
                    edited = dataclasses.replace(edited, category_id=changes.category_id)
                if note:
                    edited = dataclasses.replace(edited, note=note)
                if changes.payee_name.strip():
                    edited = self._labels.with_payee(edited, changes.payee_name)
                self._transactions.update(edited)
                if changes.add_tags or changes.remove_tags:
                    self._labels.change_tags(transaction.id, changes.add_tags, changes.remove_tags)
            for leg in legs:
                self._transactions.update(dataclasses.replace(leg, note=note))
            after = [self._get(t.id) for t in before]
            tags_after = self._labels.tag_ids_of(movements)
        new_payees = {payee.id for payee in self._payees.list()} - payees_before
        new_tags = {tag.id for tag in self._tags.list()} - tags_known
        count = len(transactions)
        self._undo.offer(
            f"Se editó {count} transacción."
            if count == 1
            else f"Se editaron {count} transacciones.",
            lambda: self._unedit(before, after, tags_before, tags_after, new_payees, new_tags),
        )

    def _get(self, transaction_id: int) -> Transaction:
        return require_found(self._transactions.get(transaction_id), "La transacción no existe.")

    def _unedit(
        self,
        before: list[Transaction],
        after: list[Transaction],
        tags_before: dict[int, list[int]],
        tags_after: dict[int, list[int]],
        new_payees: set[int],
        new_tags: set[int],
    ) -> None:
        """Undoes ``apply``: each transaction and its tags as they were, and the payees and
        tags it created gone, unless something else uses them now."""
        edited = [self._transactions.get(t.id) for t in after]
        movements = [t for t in after if t.id in tags_after]
        if edited != after or self._labels.tag_ids_of(movements) != tags_after:
            raise changed_since("Alguna de esas transacciones")
        for transaction in before:
            self._transactions.update(transaction)
        for transaction_id, tag_ids in tags_before.items():
            self._tags.set_for(transaction_id, tag_ids)
        for payee_id in new_payees:
            if self._payees.count_transactions(payee_id) == 0:
                self._payees.delete(payee_id)
        for tag_id in new_tags:
            if self._tags.count_transactions(tag_id) == 0:
                self._tags.delete(tag_id)

    def _require_category_for(self, category_id: int, movements: list[Transaction]) -> None:
        category = require_found(self._categories.get(category_id), "La categoría no existe.")
        if not movements:
            raise ValidationError("Las transferencias no tienen categoría.")
        if any(t.type is not category.kind for t in movements):
            raise ValidationError(
                f"La categoría «{category.name}» no corresponde a todas las transacciones elegidas."
            )
