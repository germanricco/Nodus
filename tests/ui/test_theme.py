import pytest
from factories import ars
from PySide6.QtGui import QFont, QFontDatabase, QFontInfo

from nodus.ui.navigation import PageId
from nodus.ui.theme.design import BOLD, FONT_FAMILY, REGULAR, SEMIBOLD
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


def test_nodus_brings_its_font_in_the_three_weights_of_the_design(theme_manager):
    """On any system, whatever fonts it has: the screens are measured in this one."""
    assert QFontInfo(QFont(FONT_FAMILY)).family() == FONT_FAMILY
    weights = {
        QFontDatabase.weight(FONT_FAMILY, style) for style in QFontDatabase.styles(FONT_FAMILY)
    }
    assert weights >= {REGULAR, SEMIBOLD, BOLD}
