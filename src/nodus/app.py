"""Application entry point."""

import ctypes
import sys
from datetime import date

from PySide6.QtWidgets import QApplication, QMessageBox

from nodus.config.paths import AppPaths
from nodus.database.database import Database, DatabaseError
from nodus.services.container import Services
from nodus.ui.event_bus import EventBus
from nodus.ui.main_window import MainWindow
from nodus.ui.theme.icons import app_icon
from nodus.ui.theme.theme import ThemeMode
from nodus.ui.theme.theme_manager import ThemeManager


class NodusApp:
    """Starts Nodus: makes sure the local database is usable, then opens the main window."""

    APPLICATION_NAME = "Nodus"
    # Lets Windows group the windows under Nodus's own taskbar icon instead of Python's.
    APP_USER_MODEL_ID = "GermanRicco.Nodus"

    def __init__(self, argv: list[str]) -> None:
        # Must be set before AppPaths, which derives the data folder from it.
        QApplication.setApplicationName(self.APPLICATION_NAME)
        self._qt_app = QApplication(argv)
        self._qt_app.setWindowIcon(app_icon())
        self._set_taskbar_identity()
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
            services = Services.create(database)
            services.backups.create_if_due(date.today())
            services.startup.repair()
            theme_mode = ThemeMode.from_setting(services.settings.theme_preference())
            theme_manager = ThemeManager(self._qt_app, theme_mode)
            window = MainWindow(services, EventBus(), theme_manager)
            window.show()
            window.check_for_updates()
            window.update_exchange_rate()
            return self._qt_app.exec()
        finally:
            database.close()

    @classmethod
    def _set_taskbar_identity(cls) -> None:
        if sys.platform == "win32":
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(cls.APP_USER_MODEL_ID)


def main() -> int:
    return NodusApp(sys.argv).run()
