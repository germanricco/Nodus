"""Generates packaging/nodus.ico, the icon of the executable and the installer, from the logo.

Each size is drawn by Qt straight from the SVG, so small sizes stay sharp instead of being
scaled down from a large bitmap. Needs the ``build`` extra (Pillow writes the ICO file).

Usage: .venv/Scripts/python scripts/make_icon.py
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402
from PySide6.QtCore import QBuffer, QIODevice  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from nodus.ui.theme.icons import APP_ICON_SIZES, logo_svg, render_svg  # noqa: E402

ICON_PATH = Path(__file__).resolve().parent.parent / "packaging" / "nodus.ico"


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
    print(f"Ícono generado en {ICON_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
