from decimal import Decimal

import pytest
from factories import ars, usd

from nodus.models.currency import Currency
from nodus.ui.widgets.amount_input import AmountInput, parse_amount


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.234,56", "1234.56"),
        ("1234,56", "1234.56"),
        ("1.234", "1234"),
        ("1.234.567", "1234567"),
        ("12.50", "12.50"),
        ("12.5", "12.5"),
        ("0,05", "0.05"),
        ("-1.500,25", "-1500.25"),
        (" 3 000 ", "3000"),
        ("42", "42"),
    ],
)
def test_parse_amount(text, expected):
    assert parse_amount(text) == Decimal(expected)


@pytest.mark.parametrize("text", ["abc", "1,2,3", "", "--5", "1.2.3,4,5", "$100"])
def test_parse_amount_rejects_invalid(text):
    with pytest.raises(ValueError):
        parse_amount(text)


def test_amount_input_round_trip(qtbot):
    field = AmountInput(Currency.ARS)
    qtbot.addWidget(field)

    field.set_money(usd("-1234.5"))

    assert field.line_edit.text() == "-1.234,50"
    assert field.money() == usd("-1234.5")


def test_empty_amount_is_zero(qtbot):
    field = AmountInput(Currency.ARS)
    qtbot.addWidget(field)

    assert field.money() == ars("0")
