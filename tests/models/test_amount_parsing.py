"""Reading typed amounts: what each text means in each currency, and what is refused."""

from decimal import Decimal

import pytest

from nodus.models.amount_parsing import (
    COMMA_FOR_DECIMALS_TEXT,
    DOTS_GROUP_THOUSANDS_TEXT,
    TOO_LARGE_TEXT,
    TOO_MANY_DECIMALS_TEXT,
    AmountTextError,
    parse_amount,
)
from nodus.models.currency import Currency
from nodus.models.money import MAX_UNITS, Money

WITH_CENTS = [c for c in Currency if c.decimals]


@pytest.mark.parametrize("currency", WITH_CENTS)
@pytest.mark.parametrize(
    ("text", "units"),
    [
        ("1.234,56", "1234.56"),
        ("1234,56", "1234.56"),
        ("1.234", "1234"),
        ("1.234.567", "1234567"),
        ("12.345.678,9", "12345678.9"),
        ("12.50", "12.50"),
        ("12.5", "12.5"),
        (".5", "0.5"),
        (",5", "0.5"),
        ("0,05", "0.05"),
        ("-1.500,25", "-1500.25"),
        (" 3 000 ", "3000"),
        ("3\N{NO-BREAK SPACE}000", "3000"),
        ("42", "42"),
        ("0", "0"),
    ],
)
def test_reads_amounts_with_cents(text, units, currency):
    assert parse_amount(text, currency) == Money.from_decimal(Decimal(units), currency)


@pytest.mark.parametrize(
    ("text", "units"),
    [("1.234", "1234"), ("15.000", "15000"), ("1.000,00", "1000"), ("-250", "-250")],
)
def test_reads_chilean_pesos_in_whole_units(text, units):
    assert parse_amount(text, Currency.CLP) == Money.from_decimal(units, Currency.CLP)


@pytest.mark.parametrize("text", ["12.50", "0,5", "1.234,56"])
def test_chilean_pesos_with_cents_are_refused(text):
    with pytest.raises(AmountTextError, match="Los pesos chilenos no llevan centavos."):
        parse_amount(text, Currency.CLP)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        # How an amount is written elsewhere: never guessed into a different one.
        ("1,234.56", COMMA_FOR_DECIMALS_TEXT),
        ("1,234,567", COMMA_FOR_DECIMALS_TEXT),
        ("1,2,3", COMMA_FOR_DECIMALS_TEXT),
        ("1,234", TOO_MANY_DECIMALS_TEXT),
        ("12,345", TOO_MANY_DECIMALS_TEXT),
        ("0,001", TOO_MANY_DECIMALS_TEXT),
        ("1234.567", DOTS_GROUP_THOUSANDS_TEXT),
        ("1.23,45", DOTS_GROUP_THOUSANDS_TEXT),
        ("1.2345", DOTS_GROUP_THOUSANDS_TEXT),
        ("1.234.56", DOTS_GROUP_THOUSANDS_TEXT),
        ("12.", DOTS_GROUP_THOUSANDS_TEXT),
    ],
)
def test_ambiguous_amounts_are_refused_with_how_to_write_them(text, message):
    with pytest.raises(AmountTextError) as raised:
        parse_amount(text, Currency.ARS)

    assert str(raised.value) == message


@pytest.mark.parametrize("text", ["abc", "", " ", "--5", "5-", "$100", ".", ",", "-", "1e5"])
def test_what_is_not_a_number_is_refused(text):
    with pytest.raises(AmountTextError, match="no es un monto válido"):
        parse_amount(text, Currency.ARS)


def test_the_largest_amount_is_read_and_one_more_is_refused():
    largest = f"{MAX_UNITS:,}".replace(",", ".")

    assert parse_amount(largest, Currency.ARS).is_storable
    with pytest.raises(AmountTextError, match=TOO_LARGE_TEXT):
        parse_amount(f"{MAX_UNITS + 1}", Currency.ARS)


@pytest.mark.parametrize("currency", list(Currency))
@pytest.mark.parametrize("cents", [0, 1, 99, 100, 123_456, -5_000_050, 10**13])
def test_what_is_shown_reads_back_as_it_was(cents, currency):
    """Money.format shows exactly what is stored: typed back, it is the same amount."""
    money = Money(cents if currency.decimals else cents // 100 * 100, currency)

    assert parse_amount(money.format_number(), currency) == money
    assert money.format() == f"{'-' if cents < 0 else ''}{currency.symbol} " + (
        money.format_number().removeprefix("-")
    )
