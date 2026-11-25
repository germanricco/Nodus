"""Reading typed amounts: what each text means in each currency, and what is refused.

Each case runs in Spanish as written and in English with the separators swapped
(«1.234,56» becomes «1,234.56»): the rules are the same, mirrored.
"""

from decimal import Decimal

import pytest

from nodus import i18n
from nodus.i18n import Language
from nodus.models.amount_parsing import (
    AmountTextError,
    decimal_separator_text,
    grouping_text,
    parse_amount,
    too_large_text,
    too_many_decimals_text,
)
from nodus.models.currency import Currency
from nodus.models.money import MAX_UNITS, Money

WITH_CENTS = [c for c in Currency if c.decimals]
_SWAPPED = str.maketrans(".,", ",.")


@pytest.fixture(params=[Language.SPANISH, Language.ENGLISH], ids=["es", "en"])
def typed(request):
    """Writes a Spanish case as it is typed in the language under test."""
    i18n.install(request.param)
    yield (
        (lambda text: text)
        if request.param is Language.SPANISH
        else (lambda text: text.translate(_SWAPPED))
    )
    i18n.install(Language.SPANISH)


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
def test_reads_amounts_with_cents(typed, text, units, currency):
    assert parse_amount(typed(text), currency) == Money.from_decimal(Decimal(units), currency)


@pytest.mark.parametrize(
    ("text", "units"),
    [("1.234", "1234"), ("15.000", "15000"), ("1.000,00", "1000"), ("-250", "-250")],
)
def test_reads_chilean_pesos_in_whole_units(typed, text, units):
    assert parse_amount(typed(text), Currency.CLP) == Money.from_decimal(units, Currency.CLP)


@pytest.mark.parametrize("text", ["12.50", "0,5", "1.234,56"])
def test_chilean_pesos_with_cents_are_refused(text):
    with pytest.raises(AmountTextError, match="Los pesos chilenos no llevan centavos."):
        parse_amount(text, Currency.CLP)


def test_in_english_chilean_pesos_with_cents_are_refused_in_english(english):
    with pytest.raises(AmountTextError, match="Chilean pesos have no cents."):
        parse_amount("12.50", Currency.CLP)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        # How an amount is written in the other language: never guessed into another one.
        ("1,234.56", decimal_separator_text),
        ("1,234,567", decimal_separator_text),
        ("1,2,3", decimal_separator_text),
        ("1,234", too_many_decimals_text),
        ("12,345", too_many_decimals_text),
        ("0,001", too_many_decimals_text),
        ("1234.567", grouping_text),
        ("1.23,45", grouping_text),
        ("1.2345", grouping_text),
        ("1.234.56", grouping_text),
        ("12.", grouping_text),
    ],
)
def test_ambiguous_amounts_are_refused_with_how_to_write_them(typed, text, message):
    with pytest.raises(AmountTextError) as raised:
        parse_amount(typed(text), Currency.ARS)

    assert str(raised.value) == message()


def test_the_messages_show_how_each_language_writes_an_amount(english):
    assert decimal_separator_text() == "Use a dot for decimals: 1,234.56."
    assert too_many_decimals_text() == "An amount has up to 2 decimals, as in 1,234.56."
    assert grouping_text() == "Commas group thousands, three digits at a time: 1,234,567."


def test_the_spanish_messages_are_as_they_were():
    assert decimal_separator_text() == "Usa coma para los decimales: 1.234,56."
    assert too_many_decimals_text() == "Un monto lleva hasta 2 decimales, como en 1.234,56."
    assert grouping_text() == "Los puntos separan los miles, de a tres cifras: 1.234.567."


@pytest.mark.parametrize("text", ["abc", "", " ", "$100", ".", ",", "-", "1e5", "5+a"])
def test_what_is_not_a_number_is_refused(text):
    with pytest.raises(AmountTextError, match="no es un monto válido"):
        parse_amount(text, Currency.ARS)


@pytest.mark.parametrize(
    ("text", "amount"),
    [
        ("1.500+2.300", "3800"),  # a ticket of several items
        ("36000/3", "12000"),  # a dinner split in three
        ("8500*1,1", "9350"),  # with the tip
        ("8500 x 1,105", "9392.50"),  # a factor may have more decimals than an amount
        ("(100+50)×2", "300"),
        ("100÷4", "25"),
        ("2+3*4", "14"),  # the usual precedence
        ("-50+100", "50"),
        ("3--2", "5"),  # minus a negative
        ("1000/3", "333.33"),  # rounded to the cent, as every amount
        ("12.50+1", "13.50"),  # each number read as a single amount is
    ],
)
def test_a_calculation_gives_its_result(text, amount):
    assert parse_amount(text, Currency.ARS) == Money.from_decimal(amount, Currency.ARS)


@pytest.mark.parametrize("text", ["1500+", "5-", "--5", "()", "(1+2", "1+2)", "2(3)", "*5"])
def test_a_calculation_with_something_missing_says_so(text):
    with pytest.raises(AmountTextError, match="le falta algo"):
        parse_amount(text, Currency.ARS)


def test_a_calculation_refuses_to_divide_by_zero():
    with pytest.raises(AmountTextError, match="dividir por cero"):
        parse_amount("1000/(5-5)", Currency.ARS)


def test_a_calculation_follows_the_amount_rules_for_its_numbers_and_its_result():
    with pytest.raises(AmountTextError, match="de a tres cifras"):
        parse_amount("1.23.4+1", Currency.ARS)
    with pytest.raises(AmountTextError, match="demasiado grande"):
        parse_amount(f"{MAX_UNITS}*2", Currency.ARS)
    assert parse_amount("1000/3", Currency.CLP) == Money.from_decimal("333", Currency.CLP)


def test_the_largest_amount_is_read_and_one_more_is_refused(typed):
    largest = typed(f"{MAX_UNITS:,}".replace(",", "."))

    assert parse_amount(largest, Currency.ARS).is_storable
    with pytest.raises(AmountTextError, match=too_large_text()):
        parse_amount(f"{MAX_UNITS + 1}", Currency.ARS)


@pytest.mark.parametrize("currency", list(Currency))
@pytest.mark.parametrize("cents", [0, 1, 99, 100, 123_456, -5_000_050, 10**13])
def test_what_is_shown_reads_back_as_it_was(typed, cents, currency):
    """Money.format shows exactly what is stored: typed back, it is the same amount."""
    money = Money(cents if currency.decimals else cents // 100 * 100, currency)

    assert parse_amount(money.format_number(), currency) == money
