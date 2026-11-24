"""The initial of a name in a soft circle of its color."""

import pytest

from nodus.ui.theme.design import ControlSize
from nodus.ui.widgets.initial_badge import icon_badge_pixmap, initial_of, initial_pixmap


@pytest.mark.parametrize(
    ("name", "initial"),
    [("Coto", "C"), ("  ñandú", "Ñ"), ("¡Hola!", "H"), ("7 Eleven", "7"), ("—", "·"), ("", "·")],
)
def test_the_initial_is_the_first_letter_or_digit(name, initial):
    assert initial_of(name) == initial


def test_a_badge_is_as_big_as_an_accounts_currency(qtbot):
    pixmap = initial_pixmap("Coto", "#e74c3c")
    assert pixmap.deviceIndependentSize().toSize().width() == ControlSize.BADGE


def test_an_icon_badge_draws_its_icon_where_the_letter_would_go(qtbot):
    """A transfer's badge: the same circle, with the icon inked in its center."""
    pixmap = icon_badge_pixmap("transfer", "#e74c3c")
    image = pixmap.toImage()
    ratio = pixmap.devicePixelRatio()
    center = image.pixelColor(round(16 * ratio), round(12 * ratio))
    corner = image.pixelColor(0, 0)

    assert pixmap.deviceIndependentSize().toSize().width() == ControlSize.BADGE
    assert corner.alpha() == 0
    assert center.alpha() > 0
