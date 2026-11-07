from datetime import date, timedelta
from decimal import Decimal

from factories import TODAY, ars, eur, expense_draft, income_draft, usd

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.models.period import Month, Period
from nodus.services.transaction_service import TransferDraft


def test_without_accounts_everything_is_zero(services):
    net_worth = services.net_worth.net_worth(TODAY)

    assert net_worth.by_currency == {Currency.ARS: ars("0"), Currency.USD: usd("0")}
    assert net_worth.total_in == {Currency.ARS: ars("0"), Currency.USD: usd("0")}


def test_single_currency_needs_no_rate(services, pesos):
    net_worth = services.net_worth.net_worth(TODAY)

    assert net_worth.total_in[Currency.ARS] == ars("100000")
    assert net_worth.total_in[Currency.USD] is None


def test_mixed_currencies_without_rate_cannot_be_totaled(services, pesos, dollars):
    net_worth = services.net_worth.net_worth(TODAY)

    assert net_worth.by_currency == {Currency.ARS: ars("100000"), Currency.USD: usd("500")}
    assert net_worth.total_in == {Currency.ARS: None, Currency.USD: None}


def test_mixed_currencies_are_converted_with_the_rate(services, pesos, dollars):
    services.exchange_rates.set_rate(TODAY, Decimal("1000"))

    net_worth = services.net_worth.net_worth(TODAY)

    assert net_worth.total_in == {Currency.ARS: ars("600000"), Currency.USD: usd("600")}


def test_archived_accounts_are_left_out(services, pesos, dollars):
    services.accounts.set_archived(dollars.id, True)

    net_worth = services.net_worth.net_worth(TODAY)

    assert net_worth.by_currency[Currency.USD] == usd("0")
    assert net_worth.total_in[Currency.ARS] == ars("100000")


def test_net_worth_uses_the_balances_of_that_day(services, pesos):
    services.transactions.create(expense_draft(services, pesos.id, ars("30000"), on=TODAY))

    assert services.net_worth.net_worth(TODAY - timedelta(days=1)).total_in[Currency.ARS] == ars(
        "100000"
    )
    assert services.net_worth.net_worth(TODAY).total_in[Currency.ARS] == ars("70000")


def test_balances_on_a_day_count_both_legs_of_a_transfer(services, pesos, dollars):
    services.transactions.create_transfer(
        TransferDraft(pesos.id, dollars.id, ars("100000"), TODAY, amount_in=usd("100"))
    )

    before = services.accounts.balances(TODAY - timedelta(days=1))
    after = services.accounts.balances(TODAY)

    assert (before[pesos.id], before[dollars.id]) == (ars("100000"), usd("500"))
    assert (after[pesos.id], after[dollars.id]) == (ars("0"), usd("600"))


def test_history_is_daily_for_a_month_and_stops_today(services, pesos):
    services.transactions.create(
        income_draft(services, pesos.id, ars("50000"), on=date(2026, 11, 3))
    )
    services.transactions.create(expense_draft(services, pesos.id, ars("1"), on=date(2026, 11, 20)))

    points = services.net_worth.history(Period.of_months(Month(2026, 11)), TODAY)

    assert [p.day for p in points] == [date(2026, 11, d) for d in range(1, 6)]
    totals = [p.net_worth.total_in[Currency.ARS] for p in points]
    assert totals == [ars("100000")] * 2 + [ars("150000")] * 3


def test_history_starts_from_the_balance_before_the_period(services, pesos):
    services.transactions.create(
        expense_draft(services, pesos.id, ars("40000"), on=date(2026, 10, 15))
    )

    points = services.net_worth.history(Period.of_months(Month(2026, 11)), TODAY)

    assert points[0].net_worth.total_in[Currency.ARS] == ars("60000")


def test_history_of_a_long_period_has_month_ends(services, pesos):
    period = Period.of_months(Month(2026, 1), Month(2026, 12))

    points = services.net_worth.history(period, TODAY)

    assert [p.day for p in points] == [Month(2026, m).end for m in range(1, 11)] + [TODAY]


def test_month_ends_of_a_short_period(services, pesos):
    services.transactions.create(
        expense_draft(services, pesos.id, ars("30000"), on=date(2026, 10, 15))
    )
    period = Period.of_months(Month(2026, 9), Month(2026, 11))

    points = services.net_worth.month_ends(period, TODAY)

    assert [p.day for p in points] == [Month(2026, 9).end, Month(2026, 10).end, TODAY]
    totals = [p.net_worth.total_in[Currency.ARS] for p in points]
    assert totals == [ars("100000"), ars("70000"), ars("70000")]


def test_history_without_a_rate_leaves_a_gap(services, pesos, dollars):
    services.exchange_rates.set_rate(date(2026, 11, 3), Decimal("1000"))

    points = services.net_worth.history(Period.of_months(Month(2026, 11)), TODAY)

    totals = [p.net_worth.total_in[Currency.ARS] for p in points]
    assert totals == [None, None, ars("600000"), ars("600000"), ars("600000")]


def test_history_of_a_future_period_is_empty(services, pesos):
    assert services.net_worth.history(Period.of_months(Month(2027, 1)), TODAY) == []


def test_euros_add_up_in_pesos_and_dollars(services, pesos, dollars):
    services.accounts.create("Viaje", AccountType.SAVINGS, Currency.EUR, eur("200"))
    services.exchange_rates.set_rate(TODAY, Decimal("1000"))
    services.exchange_rates.set_rate(TODAY, Decimal("1100"), Currency.EUR)

    net_worth = services.net_worth.net_worth(TODAY)

    assert list(net_worth.by_currency) == [Currency.ARS, Currency.USD, Currency.EUR]
    assert net_worth.by_currency[Currency.EUR] == eur("200")
    assert net_worth.total_in == {Currency.ARS: ars("820000"), Currency.USD: usd("820")}


def test_euros_without_their_rate_leave_no_total(services, pesos, dollars):
    services.accounts.create("Viaje", AccountType.SAVINGS, Currency.EUR, eur("200"))
    services.exchange_rates.set_rate(TODAY, Decimal("1000"))

    assert services.net_worth.net_worth(TODAY).total_in == {
        Currency.ARS: None,
        Currency.USD: None,
    }
