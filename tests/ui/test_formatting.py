"""Every change shows its sign, also with the amounts hidden (ui/text/formatting.py)."""

from factories import ars

from nodus.ui.text.formatting import signed
from nodus.ui.widgets.money_label import month_change_text


def test_a_change_always_shows_its_sign():
    assert signed(ars("1500")) == "+$ 1.500,00"
    assert signed(ars("-1500")) == "-$ 1.500,00"


def test_hidden_it_keeps_the_sign_and_the_currency():
    assert signed(ars("1500"), hidden=True) == "+$ ••••"
    assert signed(ars("-1500"), hidden=True) == "-$ ••••"
    assert month_change_text(ars("-1500"), hidden=True) == "-$ •••• este mes"
