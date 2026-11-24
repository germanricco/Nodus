"""The initial of a name in a soft circle of its color, as the currency of an account.

A list of payees (and, later, of movements) is read by its names, and a letter in a
color finds a row faster than the text alone (plan 029a, 5.6). It needs no logos and no
data of its own: the initial comes from the name and the color from the category.
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPixmap

from nodus.ui.theme.contrast import TEXT_CONTRAST, blend, shade_to_contrast
from nodus.ui.theme.design import ControlSize, Opacity, TextRole, role_font
from nodus.ui.theme.theme_manager import active_theme


def initial_of(name: str) -> str:
    """The first letter or digit of ``name``, in capitals; a dot when it has none."""
    return next((char.upper() for char in name if char.isalnum()), "·")


def initial_pixmap(name: str, color: str, size: int = ControlSize.BADGE) -> QPixmap:
    """``name``'s initial in a circle of ``color``: a soft fill and the letter in the
    shade of ``color`` that reads on it as text does. A pixmap, not an icon, so a table
    shows it at its own size beside the name."""
    surface = active_theme().surface
    screen = QGuiApplication.primaryScreen()
    ratio = screen.devicePixelRatio() if screen else 1.0
    return _pixmap(initial_of(name), color, surface, size, ratio)


@lru_cache(maxsize=512)
def _pixmap(letter: str, color: str, surface: str, size: int, ratio: float) -> QPixmap:
    fill = blend(color, surface, Opacity.BADGE_FILL)
    pixmap = QPixmap(round(size * ratio), round(size * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    rect = QRectF(0, 0, size, size)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(fill))
    painter.drawEllipse(rect)
    painter.setPen(QColor(shade_to_contrast(color, fill, TEXT_CONTRAST)))
    painter.setFont(role_font(TextRole.LABEL))
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, letter)
    painter.end()
    return pixmap
