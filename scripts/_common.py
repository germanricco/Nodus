"""What the scripts share: where the project is, and Qt drawing without a screen."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def use_offscreen_qt() -> None:
    """Makes Qt draw without a screen, for captures and icons. Called before PySide6 is
    imported; on Windows the offscreen platform needs to be told where the fonts are."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if sys.platform == "win32":
        os.environ.setdefault("QT_QPA_FONTDIR", str(Path(os.environ["WINDIR"]) / "Fonts"))
