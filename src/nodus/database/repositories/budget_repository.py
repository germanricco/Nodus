"""Persistence of monthly budget limits and their history."""

from __future__ import annotations

from nodus.database.repositories.base import Repository
from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.period import Month


def month_key(month: Month) -> str:
    """How a month is stored: "2026-11", which sorts as text in calendar order."""
    return f"{month.year:04d}-{month.month:02d}"


class BudgetRepository(Repository):
    """Limits are always in pesos, so only their cents are stored."""

    CURRENCY = Currency.ARS

    def set(self, category_id: int, month: Month, amount: Money | None) -> None:
        """Sets the limit of ``category_id`` from ``month`` on; None removes it from then."""
        self._execute(
            "INSERT INTO budget_limits (category_id, start_month, amount_cents) VALUES (?, ?, ?)"
            " ON CONFLICT (category_id, start_month)"
            " DO UPDATE SET amount_cents = excluded.amount_cents",
            (category_id, month_key(month), amount.cents if amount else None),
        )

    def limits_on(self, month: Month) -> dict[int, Money]:
        """The limit of each category with a budget in ``month``: its latest row up to it."""
        rows = self._fetch_all(
            "SELECT b.category_id, b.amount_cents FROM budget_limits b"
            " WHERE b.start_month = (SELECT MAX(start_month) FROM budget_limits"
            "   WHERE category_id = b.category_id AND start_month <= ?)"
            " AND b.amount_cents IS NOT NULL",
            (month_key(month),),
        )
        return {row["category_id"]: Money(row["amount_cents"], self.CURRENCY) for row in rows}
