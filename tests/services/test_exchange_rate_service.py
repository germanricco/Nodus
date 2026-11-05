from datetime import date
from decimal import Decimal

import pytest
from factories import ars, usd

from nodus.models.currency import Currency
from nodus.services.errors import ValidationError

OCT_1 = date(2026, 10, 1)
OCT_15 = date(2026, 10, 15)
NOV_1 = date(2026, 11, 1)


def test_rate_on_uses_latest_rate_not_after_the_day(services):
    services.exchange_rates.set_rate(OCT_1, Decimal("1100"))
    services.exchange_rates.set_rate(NOV_1, Decimal("1250"))

    assert services.exchange_rates.rate_on(OCT_15).rate == Decimal("1100")
    assert services.exchange_rates.rate_on(NOV_1).rate == Decimal("1250")
    assert services.exchange_rates.rate_on(date(2026, 9, 1)) is None


def test_setting_same_day_replaces_rate(services):
    first = services.exchange_rates.set_rate(OCT_1, Decimal("1100"))
    second = services.exchange_rates.set_rate(OCT_1, Decimal("1150.50"))

    assert first.id == second.id
    assert [r.rate for r in services.exchange_rates.history()] == [Decimal("1150.50")]


def test_history_is_newest_first(services):
    services.exchange_rates.set_rate(OCT_1, Decimal("1100"))
    services.exchange_rates.set_rate(NOV_1, Decimal("1250"))

    assert [r.rate_date for r in services.exchange_rates.history()] == [NOV_1, OCT_1]


def test_delete(services):
    rate = services.exchange_rates.set_rate(OCT_1, Decimal("1100"))

    services.exchange_rates.delete(rate.id)

    assert services.exchange_rates.history() == []


@pytest.mark.parametrize("value", ["0", "-1"])
def test_rejects_non_positive_rate(services, value):
    with pytest.raises(ValidationError):
        services.exchange_rates.set_rate(OCT_1, Decimal(value))


class TestConvert:
    def test_both_directions(self, services):
        services.exchange_rates.set_rate(OCT_1, Decimal("1200"))

        assert services.exchange_rates.convert(usd("10"), Currency.ARS, OCT_15) == ars("12000")
        assert services.exchange_rates.convert(ars("6000"), Currency.USD, OCT_15) == usd("5")

    def test_same_currency_needs_no_rate(self, services):
        assert services.exchange_rates.convert(ars("10"), Currency.ARS, OCT_1) == ars("10")

    def test_without_rate_returns_none(self, services):
        assert services.exchange_rates.convert(usd("10"), Currency.ARS, OCT_1) is None
