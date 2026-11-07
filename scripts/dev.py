"""Opens Nodus from the source code over a copy of the real data, for quick manual testing.

The copy goes to ``dev-data/`` (ignored by git). The real database is opened read-only,
so it is never modified, even while the installed Nodus has it open.

    .venv/Scripts/python scripts/dev.py           # fresh copy of the real data
    .venv/Scripts/python scripts/dev.py --keep    # reuse the previous copy and its changes
    .venv/Scripts/python scripts/dev.py --demo    # demo data instead of the real data
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

from demo_data import load_demo_data
from PySide6.QtCore import QCoreApplication

from nodus.app import NodusApp
from nodus.config.paths import AppPaths
from nodus.database.database import Database
from nodus.services.container import Services

DEV_DATA_DIR = Path(__file__).resolve().parent.parent / "dev-data"


def real_database() -> Path:
    """Where the installed Nodus keeps the user's data."""
    QCoreApplication.setApplicationName(NodusApp.APPLICATION_NAME)
    return AppPaths.default().database_path


def clear_database(target: Path) -> None:
    """Removes the previous copy, with its write-ahead log, before writing a new one."""
    for suffix in ("", "-wal", "-shm"):
        Path(f"{target}{suffix}").unlink(missing_ok=True)


def copy_real_data(source: Path, target: Path) -> None:
    """Copies ``source`` consistently, changes still in its write-ahead log included.

    SQLite's backup API reads the database as one snapshot; read-only mode guarantees
    the original is not touched.
    """
    original = sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)
    copy = sqlite3.connect(target)
    try:
        original.backup(copy)
    finally:
        copy.close()
        original.close()


def create_demo_data(target: Path) -> None:
    database = Database.open(target)
    try:
        load_demo_data(Services.create(database), date.today())
    finally:
        database.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--keep", action="store_true", help="reuse the previous copy")
    mode.add_argument("--demo", action="store_true", help="start over with demo data")
    args = parser.parse_args()

    paths = AppPaths(DEV_DATA_DIR)
    paths.ensure_data_dir()
    target = paths.database_path
    if args.keep and not target.exists():
        print("No hay una copia anterior; se copian los datos reales.")
        args.keep = False
    if not args.keep:
        clear_database(target)
        if args.demo:
            create_demo_data(target)
            print("Datos de demostración en", DEV_DATA_DIR)
        else:
            source = real_database()
            if not source.exists():
                print(f"No se encontraron datos reales en {source}.", file=sys.stderr)
                return 1
            copy_real_data(source, target)
            print(f"Copia de {source} en {DEV_DATA_DIR}")

    environment = {**os.environ, AppPaths.DATA_DIR_ENV_VAR: str(DEV_DATA_DIR)}
    return subprocess.run([sys.executable, "-m", "nodus"], env=environment).returncode


if __name__ == "__main__":
    sys.exit(main())
