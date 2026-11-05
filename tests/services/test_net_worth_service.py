from decimal import Decimal

from factories import TODAY, ars, usd

from nodus.models.currency import Currency


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
