"""Business rules for transactions and transfers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from nodus.database.database import Database
from nodus.database.repositories.account_repository import AccountRepository
from nodus.database.repositories.category_repository import CategoryRepository
from nodus.database.repositories.transaction_repository import (
    TransactionFilter,
    TransactionRepository,
)
from nodus.models.account import Account
from nodus.models.money import Money
from nodus.models.transaction import Transaction, TransactionType, Transfer
from nodus.services.errors import ValidationError, require_found


@dataclass(frozen=True)
class TransactionDraft:
    """What the user fills in for an income or an expense."""

    account_id: int
    type: TransactionType
    amount: Money
    occurred_on: date
    category_id: int
    note: str = ""


@dataclass(frozen=True)
class TransferDraft:
    """What the user fills in for a transfer between two of their accounts.

    ``amount_in`` is required only between accounts of different currencies (for example,
    buying dollars), where it records the actual rate obtained. Otherwise it is
    ``amount_out``.
    """

    from_account_id: int
    to_account_id: int
    amount_out: Money
    occurred_on: date
    amount_in: Money | None = None
    note: str = ""


class TransactionService:
    def __init__(
        self,
        database: Database,
        transactions: TransactionRepository,
        accounts: AccountRepository,
        categories: CategoryRepository,
    ) -> None:
        self._database = database
        self._transactions = transactions
        self._accounts = accounts
        self._categories = categories

    # Income and expenses

    def create(self, draft: TransactionDraft) -> Transaction:
        transaction = self._build_transaction(None, draft)
        with self._database.transaction():
            return self._transactions.add(transaction)

    def validated(self, draft: TransactionDraft) -> Transaction:
        """The transaction ``draft`` describes, checked against the rules but not saved, for
        services that save it together with other changes."""
        return self._build_transaction(None, draft)

    def update(self, transaction_id: int, draft: TransactionDraft) -> None:
        if self.get(transaction_id).is_transfer:
            raise ValidationError("Las transferencias se editan como transferencia.")
        transaction = self._build_transaction(transaction_id, draft)
        with self._database.transaction():
            self._transactions.update(transaction)

    def delete(self, transaction_id: int) -> None:
        """Deletes a transaction. Deleting either leg of a transfer deletes the whole transfer."""
        transaction = self.get(transaction_id)
        with self._database.transaction():
            if transaction.is_transfer:
                self._transactions.delete_transfer(transaction.transfer_id)
            else:
                self._transactions.delete(transaction_id)

    def get(self, transaction_id: int) -> Transaction:
        return require_found(self._transactions.get(transaction_id), "La transacción no existe.")

    def list_transactions(self, criteria: TransactionFilter) -> list[Transaction]:
        return self._transactions.list(criteria)

    # Transfers

    def create_transfer(self, draft: TransferDraft) -> Transfer:
        transfer = self._build_transfer(uuid.uuid4().hex, draft)
        with self._database.transaction():
            return Transfer(
                outgoing=self._transactions.add(transfer.outgoing),
                incoming=self._transactions.add(transfer.incoming),
            )

    def update_transfer(self, transfer_id: str, draft: TransferDraft) -> None:
        """Rewrites both legs in place, keeping their ids."""
        current = self.get_transfer(transfer_id)
        transfer = self._build_transfer(
            transfer_id, draft, leg_ids=(current.outgoing.id, current.incoming.id)
        )
        with self._database.transaction():
            self._transactions.update(transfer.outgoing)
            self._transactions.update(transfer.incoming)

    def get_transfer(self, transfer_id: str) -> Transfer:
        legs = self._transactions.list_transfer_legs(transfer_id)
        if len(legs) != 2:
            raise ValidationError("La transferencia no existe.")
        outgoing, incoming = sorted(legs, key=lambda leg: leg.type is TransactionType.INCOME)
        return Transfer(outgoing=outgoing, incoming=incoming)

    # Validation

    def _build_transaction(
        self, transaction_id: int | None, draft: TransactionDraft
    ) -> Transaction:
        account = self._active_account(draft.account_id)
        self._require_amount_for(draft.amount, account)
        category = require_found(self._categories.get(draft.category_id), "La categoría no existe.")
        if category.kind is not draft.type:
            raise ValidationError(
                f"La categoría «{category.name}» no corresponde a este tipo de transacción."
            )
        return Transaction(
            id=transaction_id,
            account_id=account.id,
            type=draft.type,
            amount=draft.amount,
            occurred_on=draft.occurred_on,
            category_id=category.id,
            note=draft.note.strip(),
        )

    def _build_transfer(
        self,
        transfer_id: str,
        draft: TransferDraft,
        leg_ids: tuple[int | None, int | None] = (None, None),
    ) -> Transfer:
        if draft.from_account_id == draft.to_account_id:
            raise ValidationError("La cuenta de origen y la de destino deben ser distintas.")
        source = self._active_account(draft.from_account_id)
        destination = self._active_account(draft.to_account_id)
        amount_in = self._incoming_amount(draft, source, destination)
        self._require_amount_for(draft.amount_out, source)
        self._require_amount_for(amount_in, destination)
        note = draft.note.strip()
        outgoing_id, incoming_id = leg_ids
        return Transfer(
            outgoing=Transaction(
                outgoing_id, source.id, TransactionType.EXPENSE, draft.amount_out,
                draft.occurred_on, None, note, transfer_id,
            ),
            incoming=Transaction(
                incoming_id, destination.id, TransactionType.INCOME, amount_in,
                draft.occurred_on, None, note, transfer_id,
            ),
        )  # fmt: skip

    @staticmethod
    def _incoming_amount(draft: TransferDraft, source: Account, destination: Account) -> Money:
        if source.currency is destination.currency:
            if draft.amount_in is not None and draft.amount_in != draft.amount_out:
                raise ValidationError(
                    "Entre cuentas de la misma moneda, el monto que sale y el que entra"
                    " deben ser iguales."
                )
            return draft.amount_out
        if draft.amount_in is None:
            raise ValidationError("Indica el monto que entra en la cuenta de destino.")
        return draft.amount_in

    def _active_account(self, account_id: int) -> Account:
        account = require_found(self._accounts.get(account_id), "La cuenta no existe.")
        if account.is_archived:
            raise ValidationError(f"La cuenta «{account.name}» está archivada.")
        return account

    @staticmethod
    def _require_amount_for(amount: Money, account: Account) -> None:
        if amount.currency is not account.currency:
            raise ValidationError(
                f"El monto debe estar en {account.currency.value}, la moneda de «{account.name}»."
            )
        if amount.cents <= 0:
            raise ValidationError("El monto debe ser mayor que cero.")
