from datetime import date
from decimal import Decimal

import pytest
from factories import ars, clp, eur, usd

from nodus.models.account import Account, AccountType
from nodus.models.currency import Currency
from nodus.models.exchange_rate import ExchangeRate, implied_rate
from nodus.models.money import Money
from nodus.models.period import Month
from nodus.models.transaction import Transaction, TransactionType

DAY = date(2026, 11, 5)


def blue_rate(value: str = "1200") -> ExchangeRate:
    return ExchangeRate(None, DAY, Currency.USD, Currency.ARS, Decimal(value))


class TestExchangeRate:
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


class TestMonth:
    def test_bounds(self):
        assert Month(2026, 2).start == date(2026, 2, 1)
        assert Month(2026, 2).end == date(2026, 2, 28)
        assert Month(2028, 2).end == date(2028, 2, 29)

    def test_navigation_crosses_years(self):
        assert Month(2026, 12).next() == Month(2027, 1)
        assert Month(2026, 1).previous() == Month(2025, 12)
        assert Month.of(date(2026, 11, 5)) == Month(2026, 11)

    def test_rejects_invalid_month(self):
        with pytest.raises(ValueError):
            Month(2026, 13)


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        (ars("243100"), usd("200"), (Currency.USD, Currency.ARS, Decimal("1215.5"))),
        (usd("200"), ars("243100"), (Currency.USD, Currency.ARS, Decimal("1215.5"))),
        (eur("100"), usd("108"), (Currency.EUR, Currency.USD, Decimal("1.08"))),
        (clp("10000"), ars("15800"), (Currency.CLP, Currency.ARS, Decimal("1.58"))),
        (ars("1"), ars("1"), None),
        (ars("1"), usd("0"), None),
    ],
)
def test_implied_rate_is_per_unit_of_the_currency_worth_more(first, second, expected):
    rate = implied_rate(first, second)

    if expected is None:
        assert rate is None
    else:
        assert (rate.base, rate.quote, rate.value) == expected


@pytest.mark.parametrize(
    "kind, transfer_id",
    [(TransactionType.EXPENSE, None), (TransactionType.INCOME, "abc")],
)
def test_only_a_plain_income_can_be_a_refund(kind, transfer_id):
    with pytest.raises(ValueError):
        Transaction(
            None, 1, kind, ars("10"), date(2026, 11, 1),
            category_id=None if transfer_id else 1, transfer_id=transfer_id, refund_of_id=7,
        )  # fmt: skip
