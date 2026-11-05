"""Location of Nodus files on the user's machine."""

from __future__ import annotations

import os
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
        if override:
            return cls(Path(override))
        location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        return cls(Path(location))

    @property
    def database_path(self) -> Path:
        return self.data_dir / self.DATABASE_FILENAME

    def ensure_data_dir(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
