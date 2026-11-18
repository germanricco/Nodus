"""How each language writes figures: the pieces every format is built from."""

import pytest

from nodus.models.language_format import format_decimal, format_percent, grouped, with_symbol


def test_spanish_writes_figures_with_a_decimal_comma_and_spaces():
    assert grouped(1_234_567) == "1.234.567"
    assert format_decimal(9.5, 1) == "9,5"
    assert format_percent(48) == "48 %"
    assert with_symbol("US$", "10,00") == "US$ 10,00"


def test_english_writes_figures_with_a_decimal_point_and_no_spaces(english):
    assert grouped(1_234_567) == "1,234,567"
    assert format_decimal(9.5, 1) == "9.5"
    assert format_percent(48) == "48%"
    assert format_percent("<1") == "<1%"
    assert with_symbol("US$", "10.00") == "US$10.00"


@pytest.mark.parametrize(("value", "text"), [(12.0, "12"), (12.04, "12"), (9.5, "9,5")])
def test_a_whole_value_can_leave_its_zero_decimal_out(value, text):
    assert format_decimal(value, 1, drop_zero=True) == text
