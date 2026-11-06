"""Writes transactions to a CSV file that opens as a table in a Spanish Excel."""

from __future__ import annotations

import csv
from pathlib import Path

from nodus.models.period import format_date
from nodus.models.transaction import Transaction, TransactionType
from nodus.services.account_service import AccountService
from nodus.services.category_service import CategoryService

HEADER = ["Fecha", "Tipo", "Cuenta", "Categoría", "Descripción", "Monto", "Moneda"]
TRANSFER_TYPE = "Transferencia"
_TYPE_NAMES = {TransactionType.EXPENSE: "Gasto", TransactionType.INCOME: "Ingreso"}


class ExportService:
    """Turns transactions into rows a spreadsheet understands.

    Excel in Spanish expects ";" between columns and a comma in decimals, and needs the
    UTF-8 mark (BOM) to show accents right. Each transfer leg is its own row, with the
    amount signed by its effect on the account, so summing a column gives real totals.
    """

    def __init__(self, accounts: AccountService, categories: CategoryService) -> None:
        self._accounts = accounts
        self._categories = categories

    def rows(self, transactions: list[Transaction]) -> list[list[str]]:
        """One row per transaction, oldest first, without the header."""
        accounts = {a.id: a.name for a in self._accounts.list_accounts(include_archived=True)}
        categories = {c.id: c.name for c in self._categories.list_categories()}
        ordered = sorted(transactions, key=lambda t: (t.occurred_on, t.id or 0))
        return [
            [
                format_date(t.occurred_on),
                TRANSFER_TYPE if t.is_transfer else _TYPE_NAMES[t.type],
                accounts[t.account_id],
                "" if t.is_transfer else categories[t.category_id],
                t.note,
                t.signed_amount.format_plain(),
                t.amount.currency.value,
            ]
            for t in ordered
        ]

    def write_csv(self, transactions: list[Transaction], path: Path) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerow(HEADER)
            writer.writerows(self.rows(transactions))
