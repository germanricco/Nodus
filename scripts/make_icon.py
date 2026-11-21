"""Generates the program's icons from the logo: packaging/nodus.ico, of the Windows
executable and installer, and packaging/nodus.png, of the AppImage on Linux.

Each size is drawn by Qt straight from the SVG, so small sizes stay sharp instead of being
scaled down from a large bitmap. Needs the ``build`` extra (Pillow writes the ICO file).

Usage: .venv/Scripts/python scripts/make_icon.py
"""

from __future__ import annotations

import io
import sys

from _common import ROOT, use_offscreen_qt

use_offscreen_qt()

from PIL import Image  # noqa: E402
from PySide6.QtCore import QBuffer, QIODevice  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from nodus.ui.theme.icons import APP_ICON_SIZES, logo_svg, render_svg  # noqa: E402

ICON_PATH = ROOT / "packaging" / "nodus.ico"
PNG_PATH = ROOT / "packaging" / "nodus.png"  # the largest size, which Linux desktops scale


def logo_image(size: int) -> Image.Image:
    """The logo as a Pillow image of ``size`` pixels."""
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    render_svg(logo_svg(), size).save(buffer, "PNG")
    return Image.open(io.BytesIO(buffer.data().data()))


def main() -> int:
    QGuiApplication(sys.argv)
    images = [logo_image(size) for size in APP_ICON_SIZES]
    largest = images[-1]
    largest.save(
        ICON_PATH,
        format="ICO",
        sizes=[(size, size) for size in APP_ICON_SIZES],
        append_images=images[:-1],
    )
    largest.save(PNG_PATH, format="PNG")
    print(f"Íconos generados en {ICON_PATH} y {PNG_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
