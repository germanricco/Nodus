import pytest
from factories import ars, usd

from nodus.models.currency import Currency
from nodus.ui.widgets.inputs.amount_input import AmountInput
from nodus.ui.widgets.inputs.input_error import InputError


def test_an_ambiguous_amount_is_refused_under_the_field(qtbot):
    field = AmountInput(Currency.ARS)
    qtbot.addWidget(field)
    field.line_edit.setText("1,234.56")

    with pytest.raises(InputError, match="Usa coma para los decimales") as raised:
        field.money()

    assert raised.value.widget is field


def test_the_field_reads_in_its_currency(qtbot):
    field = AmountInput(Currency.CLP)
    qtbot.addWidget(field)
    field.line_edit.setText("12,50")

    with pytest.raises(InputError, match="Los pesos chilenos no llevan centavos."):
        field.money()


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
