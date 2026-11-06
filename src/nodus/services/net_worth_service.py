"""Total money across accounts, in each currency and converted, today or along a period."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from nodus.database.repositories.transaction_repository import TransactionFilter
from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.period import Period
from nodus.models.transaction import TransactionType
from nodus.services.account_service import AccountService
from nodus.services.exchange_rate_service import ExchangeRateService
from nodus.services.transaction_service import TransactionService

# Up to about a quarter, the trend has a point per day; longer periods, one per month end.
DAILY_POINTS_MAX_DAYS = 92


@dataclass(frozen=True)
class NetWorth:
    """What the user has, as of a date.

    ``by_currency`` adds the balances held in each currency without converting anything.
    ``total_in`` expresses everything in one currency; it is None for a currency when a
    conversion was needed and no exchange rate exists yet.
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
        by_currency = {currency: Money.zero(currency) for currency in Currency}
        for account in self._accounts.list_accounts():
            by_currency[account.currency] += balances[account.id]
        return self._net_worth(by_currency, day)

    def history(self, period: Period, today: date) -> list[NetWorthPoint]:
        """The net worth along ``period``, up to ``today`` (the future has no data yet).

        Daily for periods of up to ``DAILY_POINTS_MAX_DAYS``, otherwise at each month end.
        Balances are read once at the start and then advanced with the period's movements,
        instead of one query per point.
        """
        end = min(period.end, today)
        if end < period.start:
            return []
        days = self._sample_days(period, end)
        currencies = {a.id: a.currency for a in self._accounts.list_accounts()}
        balances = self._accounts.balances(period.start - timedelta(days=1))
        by_currency = {currency: Money.zero(currency) for currency in Currency}
        for account_id, currency in currencies.items():
            by_currency[currency] += balances[account_id]
        movements = self._transactions.list_transactions(
            TransactionFilter(start=period.start, end=end)
        )
        movements.sort(key=lambda t: t.occurred_on)

        points = []
        index = 0
        for day in days:
            while index < len(movements) and movements[index].occurred_on <= day:
                movement = movements[index]
                index += 1
                if movement.account_id not in currencies:  # archived account
                    continue
                income = movement.type is TransactionType.INCOME
                by_currency[movement.amount.currency] += (
                    movement.amount if income else -movement.amount
                )
            points.append(NetWorthPoint(day, self._net_worth(dict(by_currency), day)))
        return points

    @staticmethod
    def _sample_days(period: Period, end: date) -> list[date]:
        if period.days <= DAILY_POINTS_MAX_DAYS:
            return [period.start + timedelta(days=i) for i in range((end - period.start).days + 1)]
        ends = [month.end for month in period.months() if month.end < end]
        return [*ends, end]

    def _net_worth(self, by_currency: dict[Currency, Money], day: date) -> NetWorth:
        total_in = {target: self._total_in(by_currency, target, day) for target in Currency}
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
