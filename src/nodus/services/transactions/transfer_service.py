"""Transfers between the user's own accounts: two movements, one out and one in, that are
saved, edited and read as one."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from nodus.database.database import Database
from nodus.database.repositories.account_repository import AccountRepository
from nodus.database.repositories.transaction_repository import TransactionRepository
from nodus.models.account import Account
from nodus.models.money import Money
from nodus.models.transaction import Transaction, TransactionType, Transfer
from nodus.services.errors import ValidationError, require_in_calendar
from nodus.services.transactions.account_rules import active_account, require_amount_for


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


class TransferService:
    def __init__(
        self, database: Database, transactions: TransactionRepository, accounts: AccountRepository
    ) -> None:
        self._database = database
        self._transactions = transactions
        self._accounts = accounts

    def create(self, draft: TransferDraft) -> Transfer:
        transfer = self._build(uuid.uuid4().hex, draft)
        with self._database.transaction():
            return Transfer(
                outgoing=self._transactions.add(transfer.outgoing),
                incoming=self._transactions.add(transfer.incoming),
            )

    def update(self, transfer_id: str, draft: TransferDraft) -> None:
        """Rewrites both legs in place, keeping their ids."""
        current = self.get(transfer_id)
        transfer = self._build(
            transfer_id, draft, leg_ids=(current.outgoing.id, current.incoming.id)
        )
        with self._database.transaction():
            self._transactions.update(transfer.outgoing)
            self._transactions.update(transfer.incoming)

    def get(self, transfer_id: str) -> Transfer:
        legs = self._transactions.list_transfer_legs(transfer_id)
        if len(legs) != 2:
            raise ValidationError("La transferencia no existe.")
        return _paired(legs)

    def get_many(self, transfer_ids: list[str]) -> dict[str, Transfer]:
        """These transfers, by id, read together: a list shows many."""
        legs: dict[str, list[Transaction]] = {}
        for leg in self._transactions.list_legs_of(transfer_ids):
            legs.setdefault(leg.transfer_id, []).append(leg)
        return {key: _paired(pair) for key, pair in legs.items() if len(pair) == 2}

    def _build(
        self,
        transfer_id: str,
        draft: TransferDraft,
        leg_ids: tuple[int | None, int | None] = (None, None),
    ) -> Transfer:
        if draft.from_account_id == draft.to_account_id:
            raise ValidationError(
                "La cuenta de origen y la de destino deben ser distintas.", field="to_account_id"
            )
        source = active_account(self._accounts, draft.from_account_id, "from_account_id")
        destination = active_account(self._accounts, draft.to_account_id, "to_account_id")
        amount_in = _incoming_amount(draft, source, destination)
        require_amount_for(draft.amount_out, source, "amount_out")
        require_amount_for(amount_in, destination, "amount_in")
        require_in_calendar(draft.occurred_on, "occurred_on")
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


def _incoming_amount(draft: TransferDraft, source: Account, destination: Account) -> Money:
    if source.currency is destination.currency:
        if draft.amount_in is not None and draft.amount_in != draft.amount_out:
            raise ValidationError(
                "Entre cuentas de la misma moneda, el monto que sale y el que entra"
                " deben ser iguales.",
                field="amount_in",
            )
        return draft.amount_out
    if draft.amount_in is None:
        raise ValidationError(
            "Indica el monto que entra en la cuenta de destino.", field="amount_in"
        )
    return draft.amount_in


def _paired(legs: list[Transaction]) -> Transfer:
    """The two legs of a transfer as one: the expense leaves, the income arrives."""
    outgoing, incoming = sorted(legs, key=lambda leg: leg.type is TransactionType.INCOME)
    return Transfer(outgoing=outgoing, incoming=incoming)
