"""How readable one color is on another, as WCAG measures it.

Text needs a contrast of at least 4.5:1 with its background (level AA); a shape that
carries meaning, such as a category's dot or the border of a focused field, needs 3:1.
``test_contrast.py`` holds the theme's tokens to these levels, and dots in a color the
user chose get an outline when that color alone would fade into the surface.
"""

from __future__ import annotations

from PySide6.QtGui import QColor

TEXT_CONTRAST = 4.5
SHAPE_CONTRAST = 3.0
# How much each step darkens or lightens an outline until it stands out (Qt's factor).
_OUTLINE_STEP = 115


def relative_luminance(color: str) -> float:
    """The luminance of ``color`` (``#rrggbb``) from 0 (black) to 1 (white)."""
    channels = QColor(color).getRgbF()[:3]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    red, green, blue = linear
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first: str, second: str) -> float:
    """From 1 (the same color) to 21 (black on white), in either order."""
    lighter, darker = sorted((relative_luminance(first), relative_luminance(second)))[::-1]
    return (lighter + 0.05) / (darker + 0.05)


def outline_for(color: str, background: str) -> str | None:
    """A ring for a dot in ``color`` that would not stand out on ``background``: the
    same hue, shaded just enough to reach the contrast of a shape. None when the dot
    stands out by itself."""
    if contrast_ratio(color, background) >= SHAPE_CONTRAST:
        return None
    return shade_to_contrast(color, background, SHAPE_CONTRAST)


def shade_to_contrast(color: str, background: str, ratio: float) -> str:
    """``color``, or the nearest shade of its hue that reaches ``ratio`` on
    ``background``: darkened on a light background, lightened on a dark one."""
    on_light = relative_luminance(background) > 0.5
    shade = QColor(color)
    for _ in range(20):
        if contrast_ratio(shade.name(), background) >= ratio:
            break
        shade = shade.darker(_OUTLINE_STEP) if on_light else shade.lighter(_OUTLINE_STEP)
    return shade.name()


def blend(color: str, background: str, amount: float) -> str:
    """``color`` laid over ``background`` at ``amount`` (0 to 1) of opacity, as one
    opaque color, so its contrast can be measured."""
    top, bottom = QColor(color), QColor(background)
    mixed = QColor(
        round(top.red() * amount + bottom.red() * (1 - amount)),
        round(top.green() * amount + bottom.green() * (1 - amount)),
        round(top.blue() * amount + bottom.blue() * (1 - amount)),
    )
    return mixed.name()
