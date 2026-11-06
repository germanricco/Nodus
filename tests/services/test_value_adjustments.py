from datetime import timedelta

import pytest
from factories import TODAY, ars, income_draft, usd

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.models.period import Month, Period
from nodus.services.errors import ValidationError

NOVEMBER = Month.of(TODAY)


@pytest.fixture
def investment(services):
    """An investment account in pesos that started with $ 1.000.000."""
    return services.accounts.create(
        "MP Inversiones", AccountType.INVESTMENT, Currency.ARS, ars("1000000")
    )


def test_adjustment_brings_the_balance_to_the_value_given(services, investment):
    adjustment = services.accounts.adjust_value(investment.id, ars("1012300"), TODAY)

    assert adjustment.amount == ars("12300")
    assert services.accounts.balance(investment.id) == ars("1012300")
    assert services.net_worth.net_worth(TODAY).total_in[Currency.ARS] == ars("1012300")


def test_a_lower_value_is_a_negative_adjustment(services, investment):
    adjustment = services.accounts.adjust_value(investment.id, ars("990000"), TODAY)

    assert adjustment.amount == ars("-10000")
    assert services.accounts.value_change(investment.id) == ars("-10000")


def test_adjustment_is_neither_income_nor_expense(services, investment):
    services.accounts.adjust_value(investment.id, ars("1012300"), TODAY)

    summary = services.dashboard.summary(Period.of_months(NOVEMBER))
    assert summary.income == ars("0")
    assert summary.expenses == ars("0")


def test_same_value_records_nothing(services, investment):
    assert services.accounts.adjust_value(investment.id, ars("1000000"), TODAY) is None
    assert services.accounts.value_adjustments(investment.id) == []


def test_value_is_measured_against_the_balance_on_that_day(services, investment):
    services.transactions.create(income_draft(services, investment.id, ars("50000")))
    earlier = TODAY - timedelta(days=10)

    adjustment = services.accounts.adjust_value(investment.id, ars("1001000"), earlier)

    assert adjustment.amount == ars("1000")
    assert services.accounts.balance(investment.id) == ars("1051000")


def test_net_worth_history_follows_the_adjustment_from_its_day(services, investment):
    day = NOVEMBER.start + timedelta(days=2)
    services.accounts.adjust_value(investment.id, ars("1005000"), day)

    history = services.net_worth.history(Period.of_months(NOVEMBER), TODAY)

    values = {point.day: point.net_worth.total_in[Currency.ARS] for point in history}
    assert values[day - timedelta(days=1)] == ars("1000000")
    assert values[day] == ars("1005000")
    assert values[TODAY] == ars("1005000")


def test_value_change_adds_every_adjustment(services, investment):
    services.accounts.adjust_value(investment.id, ars("1010000"), TODAY - timedelta(days=30))
    services.accounts.adjust_value(investment.id, ars("1025000"), TODAY)

    assert services.accounts.value_change(investment.id) == ars("25000")
    assert [a.amount for a in services.accounts.value_adjustments(investment.id)] == [
        ars("10000"),
        ars("15000"),
    ]


def test_only_savings_and_investments_change_value(services, pesos):
    with pytest.raises(ValidationError):
        services.accounts.adjust_value(pesos.id, ars("1"), TODAY)


def test_value_goes_in_the_account_currency(services, investment):
    with pytest.raises(ValidationError):
        services.accounts.adjust_value(investment.id, usd("1000"), TODAY)


def test_deleting_an_adjustment_restores_the_balance(services, investment):
    adjustment = services.accounts.adjust_value(investment.id, ars("1012300"), TODAY)

    services.accounts.delete_adjustment(adjustment.id)

    assert services.accounts.balance(investment.id) == ars("1000000")


def test_deleting_the_account_takes_its_adjustments(services, investment):
    services.accounts.adjust_value(investment.id, ars("1012300"), TODAY)

    services.accounts.delete(investment.id)

    assert services.accounts.value_adjustments() == []
