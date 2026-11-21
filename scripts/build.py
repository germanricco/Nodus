"""Builds Nodus: the program folder with PyInstaller, then the Windows installer or, on
Linux, the AppImage.

The same command runs locally and in GitHub Actions. Needs the ``build`` extra.

Usage: .venv/Scripts/python scripts/build.py   (on Linux: .venv-linux/bin/python)
Output: dist/Nodus/ and dist/Nodus-Setup-<version>.exe on Windows,
        dist/Nodus/ and dist/Nodus-<version>-x86_64.AppImage on Linux

The built program is opened once with ``--smoke-test`` (``nodus.smoke_test``) before
it is packed, and on Linux the AppImage once more, so a piece PyInstaller left out stops
the build here.

The installer needs Inno Setup 6 (``winget install JRSoftware.InnoSetup``); without it
only the program folder is built. The AppImage tools are downloaded on the first build,
in the fixed versions below, and checked against their SHA-256.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from _common import ROOT
from translations import compile_catalogs

from nodus import APP_USER_MODEL_ID, DESKTOP_FILE_ID, __version__
from nodus.config.paths import AppPaths
from nodus.links import REPOSITORY_URL
from nodus.smoke_test import FLAG as SMOKE_TEST_FLAG

PACKAGING = ROOT / "packaging"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
# Where winget (per user) and the classic installer put the Inno Setup compiler.
ISCC_LOCATIONS = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
    Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Inno Setup 6" / "ISCC.exe",
    Path(os.environ.get("PROGRAMFILES", "")) / "Inno Setup 6" / "ISCC.exe",
]


class Download:
    """A build tool fetched from its release, the same file on every build: the version
    is fixed and the file must match the SHA-256 its release publishes."""

    def __init__(self, url: str, sha256: str) -> None:
        self.url = url
        self.sha256 = sha256

    def fetch(self) -> Path:
        """The tool in build/tools, downloaded if it is not there yet."""
        path = BUILD / "tools" / self.url.rsplit("/", 1)[-1]
        if not path.is_file() or self._digest(path) != self.sha256:
            path.parent.mkdir(parents=True, exist_ok=True)
            print(f"Descargando {self.url}")
            urllib.request.urlretrieve(self.url, path)
            if self._digest(path) != self.sha256:
                path.unlink()
                raise SystemExit(f"{path.name} no coincide con su SHA-256: no se usa.")
        path.chmod(0o755)
        return path

    @staticmethod
    def _digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()


# Packs a folder into an AppImage.
APPIMAGETOOL = Download(
    "https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage",
    "ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0",
)
# The start of every AppImage, which mounts it and opens the program. Given to
# appimagetool so it does not fetch the newest one from the internet on each build.
APPIMAGE_RUNTIME = Download(
    "https://github.com/AppImage/type2-runtime/releases/download/20251108/runtime-x86_64",
    "2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d",
)


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
            str(BUILD),
        ],
        check=True,
    )
    return DIST / "Nodus" / ("Nodus.exe" if sys.platform == "win32" else "Nodus")


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


def make_app_dir() -> Path:
    """The folder the AppImage is made of: the program in usr/lib/nodus, its ``.desktop``
    file and icon at the top, and ``AppRun``, what the AppImage opens, pointing at it."""
    app_dir = BUILD / "Nodus.AppDir"
    shutil.rmtree(app_dir, ignore_errors=True)
    shutil.copytree(DIST / "Nodus", app_dir / "usr" / "lib" / "nodus", symlinks=True)
    shutil.copy(PACKAGING / f"{DESKTOP_FILE_ID}.desktop", app_dir)
    shutil.copy(PACKAGING / "nodus.png", app_dir / f"{DESKTOP_FILE_ID}.png")
    (app_dir / "AppRun").symlink_to("usr/lib/nodus/Nodus")
    (app_dir / ".DirIcon").symlink_to(f"{DESKTOP_FILE_ID}.png")  # what file managers show
    return app_dir


def build_appimage() -> Path:
    """Packs dist/Nodus into one file that opens on most Linux distributions."""
    appimage = DIST / f"Nodus-{__version__}-x86_64.AppImage"
    subprocess.run(
        [
            str(APPIMAGETOOL.fetch()),
            "--runtime-file",
            str(APPIMAGE_RUNTIME.fetch()),
            "--no-appstream",
            str(make_app_dir()),
            str(appimage),
        ],
        # appimagetool is an AppImage too: unpacked to run, it needs no FUSE on the machine.
        env={**os.environ, "ARCH": "x86_64", "APPIMAGE_EXTRACT_AND_RUN": "1"},
        check=True,
    )
    return appimage


def package_for_windows() -> int:
    iscc = find_iscc()
    if iscc is None:
        print("No se encontró Inno Setup 6: se armó solo la carpeta del programa.")
        return 0
    print(f"Instalador listo en {build_installer(iscc)}")
    return 0


def package_for_linux() -> int:
    appimage = build_appimage()
    if not passes_smoke_test(appimage):
        print("El AppImage no abrió entero, aunque la carpeta del programa sí.")
        return 1
    print(f"AppImage listo en {appimage}")
    return 0


def main() -> int:
    compile_catalogs()  # the .mo that PyInstaller packs with the program
    executable = build_program()
    if not passes_smoke_test(executable):
        print("El programa compilado no abrió entero: falta algo en nodus.spec.")
        return 1
    print(f"Programa listo en {executable}")
    return package_for_windows() if sys.platform == "win32" else package_for_linux()


if __name__ == "__main__":
    sys.exit(main())
