"""Location of Nodus files on the user's machine."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path

from PySide6.QtCore import QStandardPaths


class AppPaths:
    """Resolves where Nodus keeps its data.

    By default this is the per-user application data folder (``%APPDATA%/Nodus`` on Windows).
    Setting ``NODUS_DATA_DIR`` points it elsewhere, so development and tests never touch
    real financial data.
    """

    DATA_DIR_ENV_VAR = "NODUS_DATA_DIR"
    DATABASE_FILENAME = "nodus.db"

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    @classmethod
    def from_environment(cls) -> AppPaths:
        """Uses ``NODUS_DATA_DIR`` if set, otherwise the OS application data folder.

        The Qt application name must be set before calling this, since Qt derives the
        default folder from it.
        """
        override = os.environ.get(cls.DATA_DIR_ENV_VAR)
        return cls(Path(override)) if override else cls.default()

    @classmethod
    def default(cls) -> AppPaths:
        """The OS application data folder, where the user's real data lives.

        The Qt application name must be set before calling this.
        """
        location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        return cls(Path(location))

    @property
    def database_path(self) -> Path:
        return self.data_dir / self.DATABASE_FILENAME

    def ensure_data_dir(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)


def visible_path(
    path: Path, environ: Mapping[str, str] = os.environ, base_prefix: str = sys.base_prefix
) -> Path:
    """Where Windows Explorer finds ``path``.

    Python from the Microsoft Store does not write to the real ``%APPDATA%``: Windows
    redirects it to a private copy inside the package folder, which only that Python sees.
    For the user to open or back up the data file, it has to be shown there.
    """
    package = _store_package_family(base_prefix)
    app_data, local_app_data = environ.get("APPDATA"), environ.get("LOCALAPPDATA")
    if package is None or not app_data or not local_app_data:
        return path
    try:
        relative = path.relative_to(app_data)
    except ValueError:
        return path
    redirected = Path(local_app_data, "Packages", package, "LocalCache", "Roaming", relative)
    return redirected if redirected.exists() else path


def _store_package_family(base_prefix: str) -> str | None:
    """ "PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0" for a Store install, else None.

    A Store Python lives in WindowsApps under its full package name,
    "<name>_<version>_<architecture>_<resource id>_<publisher id>"; the redirected folder
    is named after "<name>_<publisher id>".
    """
    folder = Path(base_prefix)
    parts = folder.name.split("_")
    if "WindowsApps" not in folder.parts or len(parts) != 5:
        return None
    return f"{parts[0]}_{parts[4]}"
