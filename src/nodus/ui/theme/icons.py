"""Loads the SVG icons tinted with theme colors."""

from __future__ import annotations

from functools import cache
from importlib import resources

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_ICON_SIZE = 20
_RENDER_SCALE = 2  # Rendered at 2x so icons stay sharp on high-DPI screens.


@cache
def _svg(name: str) -> str:
    return resources.files("nodus.ui.icons").joinpath(f"{name}.svg").read_text("utf-8")


def tinted_pixmap(name: str, color: str) -> QPixmap:
    """The icon ``name`` drawn with ``color`` instead of ``currentColor``."""
    svg = _svg(name).replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(_ICON_SIZE * _RENDER_SCALE, _ICON_SIZE * _RENDER_SCALE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(_RENDER_SCALE)
    return pixmap


def icon(name: str, color: str, checked_color: str | None = None) -> QIcon:
    """A QIcon in ``color``; checkable buttons switch to ``checked_color`` when checked."""
    result = QIcon(tinted_pixmap(name, color))
    if checked_color is not None:
        result.addPixmap(tinted_pixmap(name, checked_color), QIcon.Mode.Normal, QIcon.State.On)
    return result
