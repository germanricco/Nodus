"""Persistence of installment plans, the calendars of purchases paid in installments."""

from __future__ import annotations

import dataclasses
import sqlite3
from datetime import date

from nodus.database.repositories.base import Repository
from nodus.models.currency import Currency
from nodus.models.installment_plan import InstallmentPlan
from nodus.models.money import Money

# The total is in the currency of the account its installments come off, so it is read from
# them. A plan always has installments: a trigger deletes it with its last one.
_SELECT = (
    "SELECT ip.*, (SELECT a.currency FROM transactions t JOIN accounts a ON a.id = t.account_id"
    " WHERE t.installment_plan_id = ip.id LIMIT 1) AS currency"
    " FROM installment_plans ip"
)


class InstallmentPlanRepository(Repository):
    def add(self, plan: InstallmentPlan) -> InstallmentPlan:
        plan_id = self._insert(
            "INSERT INTO installment_plans (count, total_cents, first_due_on, settled_on)"
            " VALUES (?, ?, ?, ?)",
            self._values(plan),
        )
        return dataclasses.replace(plan, id=plan_id)

    def update(self, plan: InstallmentPlan) -> None:
        self._execute(
            "UPDATE installment_plans SET count = ?, total_cents = ?, first_due_on = ?,"
            " settled_on = ? WHERE id = ?",
            (*self._values(plan), plan.id),
        )

    def get(self, plan_id: int) -> InstallmentPlan | None:
        row = self._fetch_one(f"{_SELECT} WHERE ip.id = ?", (plan_id,))
        return self._from_row(row) if row else None

    def list(self) -> list[InstallmentPlan]:
        return [self._from_row(row) for row in self._fetch_all(f"{_SELECT} ORDER BY ip.id")]

    def delete(self, plan_id: int) -> None:
        """Deletes the plan and, by cascade, its installments."""
        self._execute("DELETE FROM installment_plans WHERE id = ?", (plan_id,))

    @staticmethod
    def _values(plan: InstallmentPlan) -> tuple:
        return (
            plan.count,
            plan.total.cents,
            plan.first_due_on.isoformat(),
            plan.settled_on.isoformat() if plan.settled_on else None,
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> InstallmentPlan:
        return InstallmentPlan(
            id=row["id"],
            count=row["count"],
            total=Money(row["total_cents"], Currency(row["currency"])),
            first_due_on=date.fromisoformat(row["first_due_on"]),
            settled_on=date.fromisoformat(row["settled_on"]) if row["settled_on"] else None,
        )
