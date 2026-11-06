"""Loads the SVG icons tinted with theme colors, and the Nodus logo."""

from __future__ import annotations

from functools import cache
from importlib import resources

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_ICON_SIZE = 20
_RENDER_SCALE = 2  # Rendered at 2x so icons stay sharp on high-DPI screens.
_LOGO = "logo"
# Sizes Windows picks from for the title bar, taskbar and Alt+Tab.
APP_ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


@cache
def _svg(name: str) -> str:
    return resources.files("nodus.ui.icons").joinpath(f"{name}.svg").read_text("utf-8")


def render_svg(svg: str, size: int, scale: int = 1) -> QPixmap:
    """``svg`` drawn into a transparent square of ``size`` logical pixels."""
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size * scale, size * scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return pixmap


def tinted_pixmap(name: str, color: str) -> QPixmap:
    """The icon ``name`` drawn with ``color`` instead of ``currentColor``."""
    return render_svg(_svg(name).replace("currentColor", color), _ICON_SIZE, _RENDER_SCALE)


def icon(name: str, color: str, checked_color: str | None = None) -> QIcon:
    """A QIcon in ``color``; checkable buttons switch to ``checked_color`` when checked."""
    result = QIcon(tinted_pixmap(name, color))
    if checked_color is not None:
        result.addPixmap(tinted_pixmap(name, checked_color), QIcon.Mode.Normal, QIcon.State.On)
    return result


def logo_svg() -> str:
    """Source of the Nodus logo, which keeps its own colors in both themes."""
    return _svg(_LOGO)


def logo_pixmap(size: int) -> QPixmap:
    return render_svg(logo_svg(), size, _RENDER_SCALE)


def app_icon() -> QIcon:
    """The logo at every size Windows asks for, each drawn sharp instead of scaled."""
    result = QIcon()
    for size in APP_ICON_SIZES:
        result.addPixmap(render_svg(logo_svg(), size))
    return result
