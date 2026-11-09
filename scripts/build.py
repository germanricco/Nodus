"""Builds Nodus for Windows: the program folder with PyInstaller, then the installer.

The same command runs locally and in GitHub Actions. Needs the ``build`` extra.

Usage: .venv/Scripts/python scripts/build.py
Output: dist/Nodus/Nodus.exe and dist/Nodus-Setup-<version>.exe

The installer needs Inno Setup 6 (``winget install JRSoftware.InnoSetup``); without it
only the program folder is built.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from nodus import APP_USER_MODEL_ID, __version__

ROOT = Path(__file__).resolve().parent.parent
PACKAGING = ROOT / "packaging"
DIST = ROOT / "dist"
# Where winget (per user) and the classic installer put the Inno Setup compiler.
ISCC_LOCATIONS = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
    Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Inno Setup 6" / "ISCC.exe",
    Path(os.environ.get("PROGRAMFILES", "")) / "Inno Setup 6" / "ISCC.exe",
]


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


def find_iscc() -> Path | None:
    on_path = shutil.which("ISCC")
    if on_path:
        return Path(on_path)
    return next((path for path in ISCC_LOCATIONS if path.is_file()), None)


def build_installer(iscc: Path) -> Path:
    """Packs dist/Nodus into the installer and returns its path."""
    subprocess.run(
        [
            str(iscc),
            f"/DAppVersion={__version__}",
            f"/DAppUserModelID={APP_USER_MODEL_ID}",
            f"/O{DIST}",
            str(PACKAGING / "nodus.iss"),
        ],
        check=True,
    )
    return DIST / f"Nodus-Setup-{__version__}.exe"


def main() -> int:
    executable = build_program()
    print(f"Programa listo en {executable}")
    iscc = find_iscc()
    if iscc is None:
        print("No se encontró Inno Setup 6: se armó solo la carpeta del programa.")
        return 0
    print(f"Instalador listo en {build_installer(iscc)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
