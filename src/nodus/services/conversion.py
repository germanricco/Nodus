"""Income and expenses in pesos, counted one way for every screen.

Each movement is converted at the rate of its day; a refund counts as less spending in
the category of the expense it pays back; transfers only move money between accounts, so
they are left out. The dashboard, the analysis, payees and tags all count from here.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from dataclasses import dataclass

from nodus.models.currency import HOME_CURRENCY
from nodus.models.money import Money
from nodus.models.period import Period
from nodus.models.transaction import Transaction, TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.accounts.exchange_rate_service import ExchangeRateService
from nodus.services.transactions.transaction_service import TransactionService


def relative_change(current: Money, previous: Money) -> float | None:
    """How much ``current`` moved from ``previous``, as a fraction (0.1 is +10 %).

    None when ``previous`` is zero: there is nothing to compare with.
    """
    if previous.is_zero:
        return None
    return (current.cents - previous.cents) / abs(previous.cents)


def savings_rate(income: Money, expenses: Money) -> float | None:
    """The share of ``income`` that was not spent (0.2 is 20 %); None without income."""
    if income.cents <= 0:
        return None
    return (income.cents - expenses.cents) / income.cents


@dataclass(frozen=True)
class ConvertedMovement:
    """An income or expense with its amount in pesos, converted at the rate of its day.

    ``kind`` and ``category_id`` are what the movement counts as. They are the
    transaction's own, except for a refund: it counts as a negative expense in the
    category of the expense it pays back, on the day the money came back.
    """

    transaction: Transaction
    amount: Money
    kind: TransactionType
    category_id: int


@dataclass(frozen=True)
class ConvertedMovements:
    """The income and expenses of a period in pesos. Dollar movements of days without a
    rate cannot be converted: they are left out and counted in ``unconverted``, so the
    screen can say so instead of showing a wrong total."""

    movements: list[ConvertedMovement]
    unconverted: int


def period_filter(period: Period) -> TransactionFilter:
    """Every transaction of ``period``."""
    return TransactionFilter(start=period.start, end=period.end)


def converted_movements(
    transactions: TransactionService,
    exchange_rates: ExchangeRateService,
    criteria: TransactionFilter,
) -> ConvertedMovements:
    """Income and expenses matching ``criteria``, in pesos; transfers only move money
    between accounts, so they are left out. Refunds are turned into less spending."""
    if criteria.is_transfer:
        return ConvertedMovements([], 0)
    listed = transactions.list_transactions(dataclasses.replace(criteria, is_transfer=False))
    return convert_movements(transactions, exchange_rates, listed)


def convert_movements(
    transactions: TransactionService,
    exchange_rates: ExchangeRateService,
    listed: Iterable[Transaction],
) -> ConvertedMovements:
    """``listed`` in pesos, as ``converted_movements`` counts them; transfers are left out."""
    movements: list[ConvertedMovement] = []
    unconverted = 0
    refunded_categories: dict[int, int] = {}
    for transaction in listed:
        if transaction.is_transfer:
            continue
        amount = exchange_rates.convert(transaction.amount, HOME_CURRENCY, transaction.occurred_on)
        if amount is None:
            unconverted += 1
        elif transaction.refund_of_id is None:
            movements.append(
                ConvertedMovement(transaction, amount, transaction.type, transaction.category_id)
            )
        else:
            expense_id = transaction.refund_of_id
            if expense_id not in refunded_categories:
                refunded_categories[expense_id] = transactions.get(expense_id).category_id
            movements.append(
                ConvertedMovement(
                    transaction, -amount, TransactionType.EXPENSE, refunded_categories[expense_id]
                )
            )
    return ConvertedMovements(movements, unconverted)


def net_in_pesos(
    transactions: list[Transaction], exchange_rates: ExchangeRateService
) -> tuple[Money, int]:
    """Income minus expenses of ``transactions`` in pesos, each at the rate of its day, and
    how many could not be converted for lack of a rate."""
    net = Money.zero(HOME_CURRENCY)
    unconverted = 0
    for transaction in transactions:
        amount = exchange_rates.convert(
            transaction.signed_amount, HOME_CURRENCY, transaction.occurred_on
        )
        if amount is None:
            unconverted += 1
        else:
            net += amount
    return net, unconverted


def positive_totals(totals: dict[int, Money]) -> list[tuple[int, Money]]:
    """The ``totals`` above zero, largest first. A category whose refunds outweigh its
    spending in a period has nothing to show for it."""
    kept = [(key, total) for key, total in totals.items() if total.cents > 0]
    return sorted(kept, key=lambda item: item[1].cents, reverse=True)


class FlowFigures:
    """What any income and expenses tell: the savings, and their share of the income.
    Mixed into every figure that has both, so they are worked out one way."""

    income: Money
    expenses: Money

    @property
    def savings(self) -> Money:
        return self.income - self.expenses

    @property
    def savings_rate(self) -> float | None:
        return savings_rate(self.income, self.expenses)


@dataclass(frozen=True)
class FlowTotals(FlowFigures):
    """Income and expenses added up."""

    income: Money
    expenses: Money


def flow_totals(movements: Iterable[ConvertedMovement]) -> FlowTotals:
    """What ``movements`` add up to, by kind."""
    totals = {kind: Money.zero(HOME_CURRENCY) for kind in TransactionType}
    for movement in movements:
        totals[movement.kind] += movement.amount
    return FlowTotals(totals[TransactionType.INCOME], totals[TransactionType.EXPENSE])
