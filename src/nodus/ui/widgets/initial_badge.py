"""The initial of a name in a soft circle of its color, as the currency of an account.

A list of payees (and, later, of movements) is read by its names, and a letter in a
color finds a row faster than the text alone (plan 029a, 5.6). It needs no logos and no
data of its own: the initial comes from the name and the color from the category.
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPixmap

from nodus.ui.theme.contrast import TEXT_CONTRAST, blend, shade_to_contrast
from nodus.ui.theme.design import ControlSize, IconSize, Opacity, TextRole, role_font
from nodus.ui.theme.icons import tinted_pixmap
from nodus.ui.theme.theme_manager import active_theme


def initial_of(name: str) -> str:
    """The first letter or digit of ``name``, in capitals; a dot when it has none."""
    return next((char.upper() for char in name if char.isalnum()), "·")


def initial_pixmap(name: str, color: str, size: int = ControlSize.BADGE) -> QPixmap:
    """``name``'s initial in a circle of ``color``: a soft fill and the letter in the
    shade of ``color`` that reads on it as text does. A pixmap, not an icon, so a table
    shows it at its own size beside the name."""
    return badge_pixmap(initial_of(name), color, size)


def badge_pixmap(letter: str, color: str, size: int = ControlSize.BADGE) -> QPixmap:
    """``letter`` in a circle of ``color``, as ``initial_pixmap`` draws an initial."""
    return _cached(letter, "", color, active_theme().surface, size, _ratio())


def icon_badge_pixmap(icon_name: str, color: str, size: int = ControlSize.BADGE) -> QPixmap:
    """The icon ``icon_name`` where the initial would go, for a row that has no name of
    its own to show, such as a transfer."""
    return _cached("", icon_name, color, active_theme().surface, size, _ratio())


def _ratio() -> float:
    screen = QGuiApplication.primaryScreen()
    return screen.devicePixelRatio() if screen else 1.0


@lru_cache(maxsize=512)
def _cached(
    letter: str, icon_name: str, color: str, surface: str, size: int, ratio: float
) -> QPixmap:
    """The soft circle with ``letter`` or ``icon_name`` in the shade of ``color`` that
    reads on it as text does."""
    fill = blend(color, surface, Opacity.BADGE_FILL)
    ink = shade_to_contrast(color, fill, TEXT_CONTRAST)
    pixmap = QPixmap(round(size * ratio), round(size * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    rect = QRectF(0, 0, size, size)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(fill))
    painter.drawEllipse(rect)
    if icon_name:
        glyph = tinted_pixmap(icon_name, ink, IconSize.M)
        offset = (size - IconSize.M) / 2
        painter.drawPixmap(QPointF(offset, offset), glyph)
    else:
        painter.setPen(QColor(ink))
        painter.setFont(role_font(TextRole.LABEL))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, letter)
    painter.end()
    return pixmap
