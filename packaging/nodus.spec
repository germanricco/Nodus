# PyInstaller recipe for Nodus: a folder with the program, Nodus.exe on Windows (without
# a console window) and Nodus on Linux. Run through scripts/build.py, which then builds the
# Windows installer or the AppImage.
# ruff: noqa: F821  (Analysis, PYZ, EXE and COLLECT are provided by PyInstaller)

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

from nodus import __version__

PACKAGING = Path(SPECPATH)
ROOT = PACKAGING.parent
VERSION_TUPLE = tuple(int(part) for part in __version__.split(".")) + (0,)


def version_resource():
    """What Windows shows in the file's Properties > Details."""
    from PyInstaller.utils.win32 import versioninfo as vi  # needs pefile, a Windows extra

    strings = [
        vi.StringStruct("CompanyName", "German Ricco"),
        vi.StringStruct("FileDescription", "Nodus"),
        vi.StringStruct("FileVersion", __version__),
        vi.StringStruct("InternalName", "Nodus"),
        vi.StringStruct("LegalCopyright", "MIT License - German Ricco"),
        vi.StringStruct("OriginalFilename", "Nodus.exe"),
        vi.StringStruct("ProductName", "Nodus"),
        vi.StringStruct("ProductVersion", __version__),
    ]
    return vi.VSVersionInfo(
        ffi=vi.FixedFileInfo(filevers=VERSION_TUPLE, prodvers=VERSION_TUPLE),
        kids=[
            vi.StringFileInfo([vi.StringTable("040904B0", strings)]),
            vi.VarFileInfo([vi.VarStruct("Translation", [0x0409, 1200])]),
        ],
    )


# Qt parts PySide6 brings along that Nodus never loads: QML and Quick (pulled in by the
# virtual keyboard plugin), PDF (by its image plugin), the software OpenGL fallback and
# Qt's own translations but qtbase_es (nodus.ui.qt_language.QT_TEXTS), which puts the menus of the
# text fields in Spanish. Leaving them out saves about 45 MB.
UNUSED_QT = (
    "opengl32sw.dll",
    "Qt6Qml",
    "Qt6Quick",
    "Qt6VirtualKeyboard",
    "Qt6Pdf",
    "qtvirtualkeyboardplugin",
    "qpdf.dll",
    "PySide6/translations/",  # Windows
    "PySide6/Qt/translations/",  # Linux
)


KEPT = ("translations/qtbase_es.qm",)

# On Linux, the GTK look of Qt (libqgtk3) and the GTK it brings, about 20 MB: Nodus draws
# its own theme, and Qt reads light or dark mode from the desktop portal without it.
GTK_LOOK = (
    "libqgtk3.so",  # the Qt plugin; the rest is GTK
    "libgtk-3.so",
    "libgdk-3.so",
    "libgdk_pixbuf-2.0.so",
    "libatk-1.0.so",
    "libatk-bridge-2.0.so",
    "libatspi.so",
    "libcairo.so",
    "libcairo-gobject.so",
    "libpango-1.0.so",
    "libpangocairo-1.0.so",
    "libpangoft2-1.0.so",
    "libepoxy.so",
    "libpixman-1.so",
    "libthai.so",
    "libdatrie.so",
    "libgraphite2.so",
    "libjpeg.so",
    "libXcomposite.so",
    "libXcursor.so",
    "libXdamage.so",
    "libXext.so",
    "libXfixes.so",
    "libXi.so",
    "libXinerama.so",
    "libXrandr.so",
    "libXrender.so",
)


def host_libraries() -> frozenset[str]:
    """What an AppImage leaves to the system it runs on (``appimage-excludelist``): the C
    and C++ runtimes, fonts and X, which the graphics driver loaded from the system needs
    in the system's own version. One built on an older Ubuntu would break it."""
    lines = (PACKAGING / "appimage-excludelist").read_text(encoding="utf-8").splitlines()
    return frozenset(line.split("#")[0].strip() for line in lines if line.split("#")[0].strip())


LEFT_TO_LINUX = host_libraries() if sys.platform == "linux" else frozenset()


def is_gtk_look(name: str) -> bool:
    """``libgtk-3.so.0`` is ``libgtk-3.so`` in any version."""
    return any(name == part or name.startswith(part + ".") for part in GTK_LOOK)


def unused(destination: str) -> bool:
    path = destination.replace("\\", "/")
    if any(path.endswith(kept) for kept in KEPT):
        return False
    name = path.rsplit("/", 1)[-1]
    if name in LEFT_TO_LINUX or (sys.platform == "linux" and is_gtk_look(name)):
        return True
    return any(part in path for part in UNUSED_QT)


analysis = Analysis(
    [str(PACKAGING / "entry.py")],
    pathex=[str(ROOT / "src")],
    # Migrations, icons, the stylesheet and the compiled catalogs (.mo; build.py compiles
    # them first, and the .po they come from stays out), which the code reads with
    # importlib.resources,
    # and the changelogs, which live at the repository root but are read from the package.
    datas=collect_data_files("nodus", excludes=["**/__pycache__", "**/*.po"])
    + [(str(ROOT / name), "nodus") for name in ("CHANGELOG.md", "CHANGELOG.en.md")],
    # Every package of Nodus, also those only read as resources (icons, fonts,
    # migrations): nothing imports them, and left out they became namespace packages,
    # whose folder is no path the stylesheet can load its images from.
    hiddenimports=collect_submodules("nodus"),
    excludes=["tkinter"],
)
analysis.binaries = [entry for entry in analysis.binaries if not unused(entry[0])]
analysis.datas = [entry for entry in analysis.datas if not unused(entry[0])]
pyz = PYZ(analysis.pure)
# The icon and the version details are part of a Windows executable; on Linux the
# AppImage carries the icon (scripts/build.py).
windows_resources = (
    {"icon": str(PACKAGING / "nodus.ico"), "version": version_resource()}
    if sys.platform == "win32"
    else {}
)
exe = EXE(
    pyz,
    analysis.scripts,
    exclude_binaries=True,
    name="Nodus",
    console=False,
    upx=False,
    **windows_resources,
)
COLLECT(exe, analysis.binaries, analysis.datas, name="Nodus", upx=False)
