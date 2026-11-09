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
    ``total_in`` expresses everything in pesos or in dollars; it is None for one of them
    when a conversion was needed and no exchange rate exists yet.
    """

    by_currency: dict[Currency, Money]
    total_in: dict[Currency, Money | None]


@dataclass(frozen=True)
class NetWorthPoint:
    """The net worth at the end of ``day``, one point of the trend chart."""

    day: date
    net_worth: NetWorth


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
        end = min(period.end, today)
        if end < period.start:
            return []
        if period.days <= DAILY_POINTS_MAX_DAYS:
            days = [period.start + timedelta(days=i) for i in range((end - period.start).days + 1)]
            return self._points(period, days)
        return self.month_ends(period, today)

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
