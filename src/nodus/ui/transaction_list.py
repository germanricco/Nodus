"""Turns stored transactions into the rows people read in lists.

A transfer is stored as two legs but is one movement for the user, so its legs collapse
into a single row. The transactions page and the dashboard share these rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from nodus.models.money import Money
from nodus.models.period import format_date
from nodus.models.transaction import Transaction, TransactionType
from nodus.services.container import Services

TRANSFER_LABEL = "Transferencia"
REFUND_MARK = "↺"


def refund_of_text(expense: Transaction, description: str) -> str:
    """ "Reembolso de «Zapatillas» del 20/10/2026"."""
    return f"Reembolso de «{description}» del {format_date(expense.occurred_on)}"


def refunded_text(amounts: list[Money]) -> str:
    """ "Reembolsado $ 400,00", or "Reembolsado $ 400,00 + US$ 2,00" across currencies."""
    return "Reembolsado " + " + ".join(amount.format() for amount in amounts)


@dataclass(frozen=True)
class TransactionListItem:
    """Display texts for one movement. ``transaction`` is the outgoing leg of a transfer."""

    transaction: Transaction
    description: str
    category_name: str
    category_color: str | None
    payee_name: str
    account_text: str
    amount_text: str
    tone: str  # "positive", "negative" or "neutral", as MoneyLabel uses it
    refund_text: str = ""  # what the refund pays back, or what was refunded of the expense

    @property
    def occurred_on(self) -> date:
        return self.transaction.occurred_on

    @property
    def is_transfer(self) -> bool:
        return self.transaction.is_transfer


class TransactionListBuilder:
    """Builds list items, looking up account and category names once per build."""

    def __init__(self, services: Services) -> None:
        self._services = services

    def build(self, transactions: list[Transaction]) -> list[TransactionListItem]:
        """One item per movement, in the order given; a transfer appears where its first leg is.

        When a filter returned only one leg of a transfer (e.g. filtering by account), the
        other leg is fetched so the row can still show both accounts.
        """
        self._account_names = {
            account.id: account.name
            for account in self._services.accounts.list_accounts(include_archived=True)
        }
        self._categories = {c.id: c for c in self._services.categories.list_categories()}
        self._payee_names = {p.id: p.name for p in self._services.payees.list_payees()}
        self._refunded = self._services.transactions.refund_totals()
        items: list[TransactionListItem] = []
        seen_transfers: set[str] = set()
        for transaction in transactions:
            if not transaction.is_transfer:
                items.append(self._regular_item(transaction))
            elif transaction.transfer_id not in seen_transfers:
                seen_transfers.add(transaction.transfer_id)
                items.append(self._transfer_item(transaction.transfer_id))
        return items

    def describe(self, transaction: Transaction) -> str:
        """The note, or the category's name when there is none."""
        return transaction.note or self._categories[transaction.category_id].name

    def _refund_text(self, transaction: Transaction) -> str:
        if transaction.refund_of_id is not None:
            expense = self._services.transactions.get(transaction.refund_of_id)
            return refund_of_text(expense, self.describe(expense))
        if transaction.id in self._refunded:
            return refunded_text(self._refunded[transaction.id])
        return ""

    def _regular_item(self, transaction: Transaction) -> TransactionListItem:
        category = self._categories[transaction.category_id]
        return TransactionListItem(
            transaction=transaction,
            description=self.describe(transaction),
            category_name=category.name,
            category_color=category.color,
            payee_name=self._payee_names.get(transaction.payee_id, ""),
            account_text=self._account_names[transaction.account_id],
            amount_text=transaction.signed_amount.format(),
            tone="positive" if transaction.type is TransactionType.INCOME else "negative",
            refund_text=self._refund_text(transaction),
        )

    def _transfer_item(self, transfer_id: str) -> TransactionListItem:
        transfer = self._services.transactions.get_transfer(transfer_id)
        outgoing, incoming = transfer.outgoing, transfer.incoming
        amount_text = outgoing.amount.format()
        if incoming.amount.currency is not outgoing.amount.currency:
            amount_text += f" → {incoming.amount.format()}"
        return TransactionListItem(
            transaction=outgoing,
            description=outgoing.note or TRANSFER_LABEL,
            category_name=TRANSFER_LABEL,
            category_color=None,
            payee_name="",
            account_text=(
                f"{self._account_names[outgoing.account_id]}"
                f" → {self._account_names[incoming.account_id]}"
            ),
            amount_text=amount_text,
            tone="neutral",
        )
