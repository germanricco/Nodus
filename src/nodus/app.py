"""Application entry point."""

import ctypes
import logging
import sys
from datetime import date

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from nodus import APP_NAME, APP_USER_MODEL_ID
from nodus.config.logs import RunLog, system_line
from nodus.config.paths import AppPaths, visible_path
from nodus.database.database import Database, DatabaseError
from nodus.services.container import Services
from nodus.ui.dialogs.user_error import user_error
from nodus.ui.error_reporter import ErrorReporter
from nodus.ui.event_bus import EventBus
from nodus.ui.shell.main_window import MainWindow
from nodus.ui.theme.design import set_reduced_motion
from nodus.ui.theme.icons import app_icon
from nodus.ui.theme.theme import ThemeMode
from nodus.ui.theme.theme_manager import ThemeManager

logger = logging.getLogger(__name__)

OPEN_FAILED = "No se pudieron abrir tus datos."
OPEN_FAILED_HOW = (
    "Cierra los programas que puedan estar usando el archivo, como un antivirus o una"
    " sincronización, y vuelve a abrir Nodus. Tus copias de seguridad están en la carpeta"
    " «backups», junto a tus datos."
)


class NodusApp:
    """Starts Nodus: makes sure the local database is usable, then opens the main window."""

    APPLICATION_NAME = APP_NAME

    def __init__(self, argv: list[str]) -> None:
        # Must be set before AppPaths, which derives the data folder from it.
        QApplication.setApplicationName(self.APPLICATION_NAME)
        self._qt_app = QApplication(argv)
        self._qt_app.setWindowIcon(app_icon())
        self._set_taskbar_identity()
        self._paths = AppPaths.from_environment()

    def run(self) -> int:
        """Runs the event loop and returns the process exit code.

        The log and the error reporter cover the whole run, opening the data included,
        so nothing that fails, even before the window, goes unseen.
        """
        self._paths.ensure_data_dir()
        run_log = RunLog(self._paths.logs_dir)
        run_log.start()
        reporter = ErrorReporter(visible_path(self._paths.logs_dir))
        reporter.install()
        logger.info("Starting: %s", system_line())
        try:
            return self._open_and_run(reporter)
        finally:
            logger.info("Closed")
            reporter.uninstall()
            run_log.stop()

    def _open_and_run(self, reporter: ErrorReporter) -> int:
        try:
            database = Database.open(self._paths.database_path)
        except DatabaseError as error:
            logger.error("The data could not be opened", exc_info=error)
            user_error(None, self.APPLICATION_NAME, OPEN_FAILED, OPEN_FAILED_HOW, str(error))
            return 1
        try:
            try:
                self._open_window(Services.create(database, self._paths.backups_dir))
            except Exception as error:  # noqa: BLE001 - shown instead of a silent exit
                logger.error("Nodus could not start", exc_info=error)
                reporter.show(error)
                return 1
            return self._qt_app.exec()
        finally:
            database.close()

    def _open_window(self, services: Services) -> None:
        """Tidies the data up, opens the window and starts what runs behind it."""
        services.backups.create_if_due(date.today())
        services.startup.repair()
        services.updates.clean()
        set_reduced_motion(services.settings.reduce_motion())
        theme_mode = ThemeMode.from_setting(services.settings.theme_preference())
        theme_manager = ThemeManager(self._qt_app, theme_mode)
        window = MainWindow(services, EventBus(), theme_manager)
        window.show()
        window.check_for_updates()
        window.update_exchange_rate()
        # Once the window has painted, so the news appear over it, not before it.
        QTimer.singleShot(0, window.show_unseen_news)

    @staticmethod
    def _set_taskbar_identity() -> None:
        """Groups the windows under Nodus's own taskbar icon instead of Python's."""
        if sys.platform == "win32":
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)


def main() -> int:
    return NodusApp(sys.argv).run()
