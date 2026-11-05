import pytest
from factories import ars

from nodus.ui.theme.icons import tinted_pixmap
from nodus.ui.theme.theme import DARK, LIGHT, ThemeMode
from nodus.ui.widgets.money_label import MoneyLabel


def test_explicit_modes_apply_their_palette(qapp, theme_manager):
    assert theme_manager.theme is LIGHT
    assert LIGHT.background in qapp.styleSheet()

    theme_manager.set_mode(ThemeMode.DARK)

    assert theme_manager.theme is DARK
    assert DARK.background in qapp.styleSheet()


def test_theme_change_is_announced(theme_manager, qtbot):
    with qtbot.waitSignal(theme_manager.theme_changed) as signal:
        theme_manager.set_mode(ThemeMode.DARK)

    assert signal.args == [DARK]


def test_stylesheet_has_no_unfilled_tokens(qapp, theme_manager):
    assert "$" not in qapp.styleSheet()


@pytest.mark.parametrize("name", ["dashboard", "accounts", "transactions", "categories", "plus"])
def test_icons_render(qapp, name):
    assert not tinted_pixmap(name, "#000000").isNull()


@pytest.mark.parametrize(
    ("amount", "highlight_positive", "tone"),
    [
        ("-1", False, "negative"),
        ("5", False, "neutral"),
        ("5", True, "positive"),
        ("0", True, "neutral"),
    ],
)
def test_money_label_tone(qtbot, amount, highlight_positive, tone):
    label = MoneyLabel(ars(amount), highlight_positive=highlight_positive)
    qtbot.addWidget(label)

    assert label.property("tone") == tone
    assert label.text() == ars(amount).format()


def test_unknown_theme_setting_falls_back_to_system():
    assert ThemeMode.from_setting(None) is ThemeMode.SYSTEM
    assert ThemeMode.from_setting("sepia") is ThemeMode.SYSTEM
    assert ThemeMode.from_setting("dark") is ThemeMode.DARK
