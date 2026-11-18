"""Builds Nodus for Windows: the program folder with PyInstaller, then the installer.

The same command runs locally and in GitHub Actions. Needs the ``build`` extra.

Usage: .venv/Scripts/python scripts/build.py
Output: dist/Nodus/Nodus.exe and dist/Nodus-Setup-<version>.exe

The built program is opened once with ``--smoke-test`` (``nodus.smoke_test``) before
the installer is made, so a piece PyInstaller left out stops the build here.

The installer needs Inno Setup 6 (``winget install JRSoftware.InnoSetup``); without it
only the program folder is built.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from _common import ROOT
from translations import compile_catalogs

from nodus import APP_USER_MODEL_ID, __version__
from nodus.config.paths import AppPaths
from nodus.links import REPOSITORY_URL
from nodus.smoke_test import FLAG as SMOKE_TEST_FLAG

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


def passes_smoke_test(executable: Path) -> bool:
    """Opens ``executable`` with ``--smoke-test`` over a throwaway data folder; True if it
    opened whole. On failure, its log tells what was missing."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        env = {**os.environ, AppPaths.DATA_DIR_ENV_VAR: folder}
        result = subprocess.run(
            [str(executable), SMOKE_TEST_FLAG], env=env, timeout=120, check=False
        )
        if result.returncode != 0:
            log = AppPaths(Path(folder)).logs_dir / "nodus.log"
            print(log.read_text(encoding="utf-8") if log.is_file() else "Sin registro.")
        return result.returncode == 0


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
            f"/DRepositoryURL={REPOSITORY_URL}",
            f"/O{DIST}",
            str(PACKAGING / "nodus.iss"),
        ],
        check=True,
    )
    return DIST / f"Nodus-Setup-{__version__}.exe"


def main() -> int:
    compile_catalogs()  # the .mo that PyInstaller packs with the program
    executable = build_program()
    if not passes_smoke_test(executable):
        print("El programa compilado no abrió entero: falta algo en nodus.spec.")
        return 1
    print(f"Programa listo en {executable}")
    iscc = find_iscc()
    if iscc is None:
        print("No se encontró Inno Setup 6: se armó solo la carpeta del programa.")
        return 0
    print(f"Instalador listo en {build_installer(iscc)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
