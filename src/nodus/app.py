"""Application entry point."""

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from nodus.config.paths import AppPaths
from nodus.database.database import Database, DatabaseError
from nodus.ui.main_window import MainWindow


class NodusApp:
    """Starts Nodus: makes sure the local database is usable, then opens the main window."""

    APPLICATION_NAME = "Nodus"

    def __init__(self, argv: list[str]) -> None:
        # Must be set before AppPaths, which derives the data folder from it.
        QApplication.setApplicationName(self.APPLICATION_NAME)
        self._qt_app = QApplication(argv)
        self._paths = AppPaths.from_environment()

    def run(self) -> int:
        """Runs the event loop and returns the process exit code."""
        self._paths.ensure_data_dir()
        try:
            database = Database.open(self._paths.database_path)
        except DatabaseError as error:
            QMessageBox.critical(
                None, self.APPLICATION_NAME, f"No se pudo abrir la base de datos.\n\n{error}"
            )
            return 1
        try:
            window = MainWindow()
            window.show()
            return self._qt_app.exec()
        finally:
            database.close()


def main() -> int:
    return NodusApp(sys.argv).run()
