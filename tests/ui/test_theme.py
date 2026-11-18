import pytest
from factories import ars
from PySide6.QtGui import QFontDatabase

from nodus.ui.navigation import PageId
from nodus.ui.theme import theme_manager as theme_manager_module
from nodus.ui.theme.icons import APP_ICON_SIZES, _svg, app_icon, tinted_pixmap
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


def test_tags_and_categories_have_their_own_drawings():
    """Etiquetas shows a tag, the shape with a hole at its tip, and Categorías a «#»."""
    tag = _svg(PageId.TAGS.icon_name)
    hash_sign = _svg(PageId.CATEGORIES.icon_name)
    assert "<circle" in tag and "<line" not in tag
    assert hash_sign.count("<line") == 4 and "<circle" not in hash_sign


def test_app_icon_has_every_windows_size(qapp):
    sizes = {size.width() for size in app_icon().availableSizes()}

    assert sizes == set(APP_ICON_SIZES)


def test_where_the_design_font_is_missing_nodus_brings_inter(qapp, monkeypatch):
    monkeypatch.setattr(theme_manager_module, "FONT_FAMILY", "Inter")

    theme_manager_module.load_bundled_fonts()

    assert "Inter" in QFontDatabase.families()
    assert {QFontDatabase.weight("Inter", style) for style in QFontDatabase.styles("Inter")} >= {
        400,
        600,
        700,
    }
