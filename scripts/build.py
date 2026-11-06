"""Builds Nodus for Windows: the program folder with PyInstaller, then the installer.

The same command runs locally and in GitHub Actions. Needs the ``build`` extra.

Usage: .venv/Scripts/python scripts/build.py
Output: dist/Nodus/Nodus.exe
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGING = ROOT / "packaging"
DIST = ROOT / "dist"


def build_program() -> Path:
    """Freezes the app into dist/Nodus and returns the path of the executable."""
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            str(PACKAGING / "nodus.spec"),
            "--noconfirm",
            "--clean",
            "--distpath",
            str(DIST),
            "--workpath",
            str(ROOT / "build"),
        ],
        check=True,
    )
    return DIST / "Nodus" / "Nodus.exe"


def main() -> int:
    executable = build_program()
    print(f"Programa listo en {executable}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
