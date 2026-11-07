# PyInstaller recipe for Nodus: a folder with Nodus.exe, without a console window.
# Run through scripts/build.py, which also builds the installer.
# ruff: noqa: F821  (Analysis, PYZ, EXE and COLLECT are provided by PyInstaller)

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.win32 import versioninfo as vi

from nodus import __version__

PACKAGING = Path(SPECPATH)
ROOT = PACKAGING.parent
VERSION_TUPLE = tuple(int(part) for part in __version__.split(".")) + (0,)


def version_resource() -> vi.VSVersionInfo:
    """What Windows shows in the file's Properties > Details."""
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
# Qt's own translations. Leaving them out saves about 45 MB.
UNUSED_QT = (
    "opengl32sw.dll",
    "Qt6Qml",
    "Qt6Quick",
    "Qt6VirtualKeyboard",
    "Qt6Pdf",
    "qtvirtualkeyboardplugin",
    "qpdf.dll",
    "PySide6/translations/",
)


def unused(destination: str) -> bool:
    path = destination.replace("\\", "/")
    return any(part in path for part in UNUSED_QT)


analysis = Analysis(
    [str(PACKAGING / "entry.py")],
    pathex=[str(ROOT / "src")],
    # Migrations, icons and the stylesheet, which the code reads with importlib.resources,
    # and the changelog, which lives at the repository root but is read from the package.
    datas=collect_data_files("nodus", excludes=["**/__pycache__"])
    + [(str(ROOT / "CHANGELOG.md"), "nodus")],
    excludes=["tkinter"],
)
analysis.binaries = [entry for entry in analysis.binaries if not unused(entry[0])]
analysis.datas = [entry for entry in analysis.datas if not unused(entry[0])]
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    exclude_binaries=True,
    name="Nodus",
    icon=str(PACKAGING / "nodus.ico"),
    version=version_resource(),
    console=False,
    upx=False,
)
COLLECT(exe, analysis.binaries, analysis.datas, name="Nodus", upx=False)
