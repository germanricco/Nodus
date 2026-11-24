"""The initial of a name in a soft circle of its color."""

import pytest

from nodus.ui.theme.design import ControlSize
from nodus.ui.widgets.initial_badge import initial_of, initial_pixmap


@pytest.mark.parametrize(
    ("name", "initial"),
    [("Coto", "C"), ("  ñandú", "Ñ"), ("¡Hola!", "H"), ("7 Eleven", "7"), ("—", "·"), ("", "·")],
)
def test_the_initial_is_the_first_letter_or_digit(name, initial):
    assert initial_of(name) == initial


def test_a_badge_is_as_big_as_an_accounts_currency(qtbot):
    pixmap = initial_pixmap("Coto", "#e74c3c")
    assert pixmap.deviceIndependentSize().toSize().width() == ControlSize.BADGE
