"""Every text and every meaningful shape of both themes reads against its background
(WCAG level AA), and every color token of the theme is part of a measured pair."""

from dataclasses import fields

import pytest

from nodus.models.palette import PALETTE
from nodus.ui.theme.contrast import (
    SHAPE_CONTRAST,
    TEXT_CONTRAST,
    contrast_ratio,
    outline_for,
)
from nodus.ui.theme.theme import DARK, LIGHT, Theme

THEMES = [LIGHT, DARK]

# (foreground, background) pairs as the interface shows them.
BACKGROUNDS = ("background", "surface", "sidebar", "hover")
TEXT_PAIRS = [
    *[(text, back) for text in ("text", "text_muted") for back in BACKGROUNDS],
    *[("accent_text", back) for back in ("surface", "background", "sidebar", "accent_soft")],
    ("on_accent", "accent"),
    ("on_accent", "accent_hover"),
    ("on_expense", "expense"),
    *[
        (tone, back)
        for tone in ("income", "expense", "warning")
        for back in ("surface", "background", f"{tone}_soft")
    ],
]
# Shapes that carry meaning: the focus and error borders, and the series of a chart.
SHAPE_PAIRS = [
    ("accent", "surface"),
    ("expense", "surface"),
    *[(f"chart_{n}", "surface") for n in range(1, 5)],
]
# Tokens that are only ever a background, or a border beside a stronger cue.
NOT_MEASURED = {"name", "border"}


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
@pytest.mark.parametrize("pair", TEXT_PAIRS, ids="-on-".join)
def test_text_reads_on_its_background(theme: Theme, pair: tuple[str, str]):
    text, background = (getattr(theme, token) for token in pair)
    assert contrast_ratio(text, background) >= TEXT_CONTRAST


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
@pytest.mark.parametrize("pair", SHAPE_PAIRS, ids="-on-".join)
def test_shapes_stand_out_from_their_background(theme: Theme, pair: tuple[str, str]):
    shape, background = (getattr(theme, token) for token in pair)
    assert contrast_ratio(shape, background) >= SHAPE_CONTRAST


def test_every_color_token_is_measured():
    """A new token cannot skip the measurement: it has to join a pair above."""
    measured = {token for pair in TEXT_PAIRS + SHAPE_PAIRS for token in pair}
    tokens = {field.name for field in fields(Theme)} - NOT_MEASURED
    assert tokens - measured == set()


def test_contrast_ratio_matches_wcag():
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21)
    assert contrast_ratio("#ffffff", "#ffffff") == pytest.approx(1)
    assert contrast_ratio("#767676", "#ffffff") == pytest.approx(4.54, abs=0.01)


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_every_palette_color_stands_out_as_a_dot(theme: Theme):
    """A color too pale for the surface keeps its fill and gets an outline that does
    stand out; one that stands out by itself gets none."""
    for color in PALETTE:
        outline = outline_for(color, theme.surface)
        if contrast_ratio(color, theme.surface) >= SHAPE_CONTRAST:
            assert outline is None
        else:
            assert contrast_ratio(outline, theme.surface) >= SHAPE_CONTRAST
