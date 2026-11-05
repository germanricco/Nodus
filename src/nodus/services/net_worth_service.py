"""Total money across accounts, in each currency and converted."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.services.account_service import AccountService
from nodus.services.exchange_rate_service import ExchangeRateService


@dataclass(frozen=True)
class NetWorth:
    """What the user has, as of a date.

    ``by_currency`` adds the balances held in each currency without converting anything.
    ``total_in`` expresses everything in one currency; it is None for a currency when a
    conversion was needed and no exchange rate exists yet.
    """

    by_currency: dict[Currency, Money]
    total_in: dict[Currency, Money | None]


class NetWorthService:
    """Combines account balances and exchange rates. Archived accounts are left out."""

    def __init__(self, accounts: AccountService, exchange_rates: ExchangeRateService) -> None:
        self._accounts = accounts
        self._exchange_rates = exchange_rates

    def net_worth(self, day: date) -> NetWorth:
        by_currency = {currency: Money.zero(currency) for currency in Currency}
        balances = self._accounts.balances()
        for account in self._accounts.list_accounts():
            by_currency[account.currency] += balances[account.id]
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
