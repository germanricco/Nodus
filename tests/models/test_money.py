from decimal import Decimal

import pytest

from nodus.models.currency import Currency
from nodus.models.money import CurrencyMismatchError, Money

ARS = Currency.ARS
USD = Currency.USD


class TestConstruction:
    @pytest.mark.parametrize(
        ("value", "expected_cents"),
        [("1234.56", 123456), (Decimal("0.1"), 10), (7, 700), ("-3.5", -350), ("0", 0)],
    )
    def test_from_decimal(self, value, expected_cents):
        assert Money.from_decimal(value, ARS).cents == expected_cents

    @pytest.mark.parametrize(
        ("value", "expected_cents"), [("0.125", 12), ("0.135", 14), ("-0.125", -12)]
    )
    def test_from_decimal_rounds_half_to_even(self, value, expected_cents):
        assert Money.from_decimal(value, ARS).cents == expected_cents

    def test_rejects_float(self):
        with pytest.raises(TypeError):
            Money.from_decimal(0.1, ARS)

    @pytest.mark.parametrize("cents", [1.5, "100", True])
    def test_rejects_non_int_cents(self, cents):
        with pytest.raises(TypeError):
            Money(cents, ARS)

    def test_zero(self):
        assert Money.zero(USD) == Money(0, USD)
        assert Money.zero(USD).is_zero

    def test_to_decimal_round_trips(self):
        assert Money.from_decimal("1234.56", ARS).to_decimal() == Decimal("1234.56")

    def test_is_immutable(self):
        money = Money(100, ARS)
        with pytest.raises(AttributeError):
            money.cents = 200


class TestArithmetic:
    def test_add(self):
        assert Money(150, ARS) + Money(250, ARS) == Money(400, ARS)

    def test_subtract(self):
        assert Money(150, ARS) - Money(250, ARS) == Money(-100, ARS)

    def test_negate(self):
        assert -Money(150, USD) == Money(-150, USD)
        assert (-Money(150, USD)).is_negative

    def test_compare(self):
        assert Money(100, ARS) < Money(200, ARS)
        assert max(Money(300, ARS), Money(200, ARS)) == Money(300, ARS)

    def test_equality_includes_currency(self):
        assert Money(100, ARS) != Money(100, USD)

    @pytest.mark.parametrize(
        "operation",
        [lambda a, b: a + b, lambda a, b: a - b, lambda a, b: a < b],
        ids=["add", "subtract", "compare"],
    )
    def test_mixing_currencies_fails(self, operation):
        with pytest.raises(CurrencyMismatchError):
            operation(Money(100, ARS), Money(100, USD))


class TestFormat:
    @pytest.mark.parametrize(
        ("money", "expected"),
        [
            (Money(123456, ARS), "$ 1.234,56"),
            (Money(1000, USD), "US$ 10,00"),
            (Money(-5, ARS), "-$ 0,05"),
            (Money(0, ARS), "$ 0,00"),
            (Money(123456789012, USD), "US$ 1.234.567.890,12"),
        ],
    )
    def test_format(self, money, expected):
        assert money.format() == expected
        assert str(money) == expected
