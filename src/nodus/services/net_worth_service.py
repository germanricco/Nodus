"""Total money across accounts, in each currency and converted, today or along a period."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from nodus.models.currency import TOTAL_CURRENCIES, Currency
from nodus.models.money import Money
from nodus.models.period import Period
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.account_service import AccountService
from nodus.services.exchange_rate_service import ExchangeRateService
from nodus.services.transaction_service import TransactionService

# Up to about a quarter, the trend has a point per day; longer periods, one per month end.
DAILY_POINTS_MAX_DAYS = 92


@dataclass(frozen=True)
class NetWorth:
    """What the user has, as of a date.

    ``by_currency`` adds the balances held in each currency without converting anything:
    pesos and dollars always, other currencies when some account holds them.
    ``total_in`` expresses everything in pesos or in dollars, at the rates of its day; it
    is None for one of them when a conversion was needed and that currency has no rate.
    """

    by_currency: dict[Currency, Money]
    total_in: dict[Currency, Money | None]


@dataclass(frozen=True)
class NetWorthPoint:
    """The net worth at the end of ``day``, one point of the trend chart."""

    day: date
    net_worth: NetWorth


def trend_days(period: Period, today: date) -> list[date]:
    """The days a trend shows along ``period``, up to ``today``: each one for up to
    ``DAILY_POINTS_MAX_DAYS``, otherwise each month end and the last day."""
    end = min(period.end, today)
    if end < period.start:
        return []
    if period.days <= DAILY_POINTS_MAX_DAYS:
        return [period.start + timedelta(days=i) for i in range((end - period.start).days + 1)]
    return [*(month.end for month in period.months() if month.end < end), end]


class NetWorthService:
    """Combines account balances and exchange rates. Archived accounts are left out."""

    def __init__(
        self,
        accounts: AccountService,
        transactions: TransactionService,
        exchange_rates: ExchangeRateService,
    ) -> None:
        self._accounts = accounts
        self._transactions = transactions
        self._exchange_rates = exchange_rates

    def net_worth(self, day: date) -> NetWorth:
        """Balances at the end of ``day``, converted at that day's rate."""
        balances = self._accounts.balances(day)
        accounts = self._accounts.list_accounts()
        by_currency = self._zeros({account.currency for account in accounts})
        for account in accounts:
            by_currency[account.currency] += balances[account.id]
        return self._net_worth(by_currency, day)

    def history(self, period: Period, today: date) -> list[NetWorthPoint]:
        """The net worth along ``period``, up to ``today`` (the future has no data yet).

        Daily for periods of up to ``DAILY_POINTS_MAX_DAYS``, otherwise at each month end.
        """
        days = trend_days(period, today)
        return self._points(period, days) if days else []

    def account_history(self, account_id: int, today: date) -> list[tuple[date, Money]]:
        """The balance of one account along its whole life, from its first movement or
        value update to ``today``, on the days ``trend_days`` picks; archived accounts
        included."""
        span = self._transactions.date_range(TransactionFilter(account_id=account_id))
        adjustments = self._accounts.value_adjustments(account_id)
        starts = [today] + ([span[0]] if span else []) + [a.occurred_on for a in adjustments[:1]]
        period = Period(min(starts), today)
        balance = self._accounts.balance(account_id, period.start - timedelta(days=1))
        changes = [
            (t.occurred_on, t.signed_amount)
            for t in self._transactions.list_transactions(
                TransactionFilter(account_id=account_id, start=period.start, end=today)
            )
        ]
        changes += [(a.occurred_on, a.amount) for a in adjustments if a.occurred_on <= today]
        changes.sort(key=lambda change: change[0])
        points, index = [], 0
        for day in trend_days(period, today):
            while index < len(changes) and changes[index][0] <= day:
                balance += changes[index][1]
                index += 1
            points.append((day, balance))
        return points

    def month_ends(self, period: Period, today: date) -> list[NetWorthPoint]:
        """The net worth at the end of each month of ``period``; the last point is today
        when the period reaches it."""
        end = min(period.end, today)
        if end < period.start:
            return []
        ends = [month.end for month in period.months() if month.end < end]
        return self._points(period, [*ends, end])

    def _points(self, period: Period, days: list[date]) -> list[NetWorthPoint]:
        """The net worth at the end of each of ``days``, in order within ``period``.

        Balances are read once at the start and then advanced with the period's movements,
        instead of one query per point.
        """
        end = days[-1]
        currencies = {a.id: a.currency for a in self._accounts.list_accounts()}
        balances = self._accounts.balances(period.start - timedelta(days=1))
        by_currency = self._zeros(set(currencies.values()))
        for account_id, currency in currencies.items():
            by_currency[currency] += balances[account_id]
        # Every change to a balance in the period: movements and value adjustments.
        changes = [
            (t.occurred_on, t.account_id, t.signed_amount)
            for t in self._transactions.list_transactions(
                TransactionFilter(start=period.start, end=end)
            )
        ]
        changes += [
            (a.occurred_on, a.account_id, a.amount)
            for a in self._accounts.value_adjustments(period=Period(period.start, end))
        ]
        changes.sort(key=lambda change: change[0])

        points = []
        index = 0
        for day in days:
            while index < len(changes) and changes[index][0] <= day:
                _day, account_id, amount = changes[index]
                index += 1
                if account_id in currencies:  # archived accounts are left out
                    by_currency[amount.currency] += amount
            points.append(NetWorthPoint(day, self._net_worth(dict(by_currency), day)))
        return points

    def rate_effect(self, end: NetWorthPoint, start_day: date, target: Currency) -> Money | None:
        """How much of the change in ``target`` since ``start_day`` comes from the rates
        moving, not from the user's movements: what is held at the end, valued at the end's
        rates minus at those of ``start_day``. None when a rate is missing.

        Each day is valued at its own rate, so the same history can rise in pesos and fall
        in dollars; this is the part that tells them apart.
        """
        at_end = end.net_worth.total_in[target]
        at_start = self._total_in(end.net_worth.by_currency, target, start_day)
        if at_end is None or at_start is None:
            return None
        return at_end - at_start

    @staticmethod
    def _zeros(held: set[Currency]) -> dict[Currency, Money]:
        """Zero in pesos, dollars and each currency in ``held``, in the currencies' order."""
        return {c: Money.zero(c) for c in Currency if c in TOTAL_CURRENCIES or c in held}

    def _net_worth(self, by_currency: dict[Currency, Money], day: date) -> NetWorth:
        total_in = {target: self._total_in(by_currency, target, day) for target in TOTAL_CURRENCIES}
        return NetWorth(by_currency, total_in)

    def _total_in(
        self, by_currency: dict[Currency, Money], target: Currency, day: date
    ) -> Money | None:
        total = Money.zero(target)
        for amount in by_currency.values():
            if amount.is_zero:
                continue
            converted = self._exchange_rates.convert(amount, target, day)
            if converted is None:
                return None
            total += converted
        return total
