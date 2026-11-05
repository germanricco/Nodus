from datetime import date
from decimal import Decimal

import pytest
from factories import ars, usd

from nodus.models.account import Account, AccountType
from nodus.models.currency import Currency
from nodus.models.exchange_rate import ExchangeRate
from nodus.models.money import Money
from nodus.models.transaction import Transaction, TransactionType

DAY = date(2026, 11, 5)


def blue_rate(value: str = "1200") -> ExchangeRate:
    return ExchangeRate(None, DAY, Currency.USD, Currency.ARS, Decimal(value))


class TestExchangeRate:
    def test_converts_base_to_quote(self):
        assert blue_rate().convert(usd("10")) == ars("12000")

    def test_converts_quote_to_base_rounding_to_cent(self):
        assert blue_rate("1200").convert(ars("1000")) == usd("0.83")

    @pytest.mark.parametrize("value", ["0", "-5"])
    def test_rejects_non_positive_rate(self, value):
        with pytest.raises(ValueError):
            blue_rate(value)

    def test_rejects_same_currency(self):
        with pytest.raises(ValueError):
            ExchangeRate(None, DAY, Currency.ARS, Currency.ARS, Decimal("1"))


class TestTransaction:
    def make(self, **overrides) -> Transaction:
        values = dict(
            id=None, account_id=1, type=TransactionType.EXPENSE, amount=ars("10"),
            occurred_on=DAY, category_id=1,
        )  # fmt: skip
        return Transaction(**(values | overrides))

    def test_signed_amount(self):
        assert self.make().signed_amount == ars("-10")
        assert self.make(type=TransactionType.INCOME).signed_amount == ars("10")

    def test_rejects_non_positive_amount(self):
        with pytest.raises(ValueError):
            self.make(amount=Money.zero(Currency.ARS))

    @pytest.mark.parametrize(
        ("category_id", "transfer_id"), [(None, None), (1, "abc")], ids=["neither", "both"]
    )
    def test_needs_exactly_category_or_transfer(self, category_id, transfer_id):
        with pytest.raises(ValueError):
            self.make(category_id=category_id, transfer_id=transfer_id)


def test_account_initial_balance_must_match_currency():
    with pytest.raises(ValueError):
        Account(None, "Caja", AccountType.CASH, Currency.ARS, usd("1"))
