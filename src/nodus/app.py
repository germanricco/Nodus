"""Application entry point."""

import ctypes
import logging
import sys
from collections.abc import Callable
from datetime import date, datetime

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from nodus import APP_NAME, APP_USER_MODEL_ID, DESKTOP_FILE_ID
from nodus.config.logs import RunLog, system_line
from nodus.config.paths import AppPaths, visible_path
from nodus.database.database import (
    DamagedDatabaseError,
    Database,
    DatabaseError,
    MigrationError,
    NewerDatabaseError,
)
from nodus.database.repositories.settings_repository import SettingsRepository
from nodus.i18n import N_, Language, _, install
from nodus.links import DOWNLOAD_URL
from nodus.services.app.settings_service import SettingsService
from nodus.services.backups.recovery import DataRecovery
from nodus.services.container import Services
from nodus.services.external.desktop_entry import DesktopEntry
from nodus.services.external.process import launch_detached, restart_command
from nodus.smoke_test import FLAG as SMOKE_TEST_FLAG
from nodus.smoke_test import SmokeTest
from nodus.ui.browser import open_url
from nodus.ui.dialogs.recovery_dialog import offer_recovery
from nodus.ui.dialogs.user_error import UnexpectedErrorDialog, UserErrorDialog, user_error
from nodus.ui.error_reporter import ErrorReporter
from nodus.ui.event_bus import EventBus
from nodus.ui.qt_language import QtLanguage, system_language
from nodus.ui.restart import RESTART_EXIT_CODE
from nodus.ui.shell.main_window import MainWindow
from nodus.ui.shell.single_instance import SingleInstance
from nodus.ui.theme.design import set_reduced_motion
from nodus.ui.theme.icons import app_icon
from nodus.ui.theme.theme import ThemeMode
from nodus.ui.theme.theme_manager import ThemeManager

logger = logging.getLogger(__name__)

OPEN_FAILED = N_("No se pudieron abrir tus datos.")
OPEN_FAILED_HOW = N_(
    "Cierra los programas que puedan estar usando el archivo, como un antivirus o una"
    " sincronización, y vuelve a abrir Nodus. Tus copias de seguridad están en la carpeta"
    " «backups», junto a tus datos."
)
NEWER_DATA = N_("Tus datos son de una versión más nueva de Nodus.")
NEWER_DATA_HOW = N_(
    "Esta versión no conoce todo lo que guardaste con la nueva, así que no los abre para no"
    " dañarlos. Instala la última versión de Nodus; tus datos siguen intactos."
)
DOWNLOAD = N_("Descargar Nodus")
UPDATE_FAILED = N_("No se pudieron actualizar tus datos a esta versión de Nodus.")
UPDATE_FAILED_HOW = N_(
    "Tus datos siguen como estaban, y Nodus guardó una copia de antes de actualizarlos."
    " Envía el reporte para que lo arreglemos; mientras tanto, puedes volver a instalar la"
    " versión que usabas."
)
ALREADY_OPEN = N_("Nodus ya está abierto.")
ALREADY_OPEN_HOW = N_(
    "Búscalo en la barra de tareas. Si no responde, ciérralo desde el Administrador de"
    " tareas y vuelve a abrirlo."
)
ASFW_ANY = -1  # lets any process, here the open Nodus, take the foreground


class NodusApp:
    """Starts Nodus: makes sure the local database is usable, then opens the main window."""

    APPLICATION_NAME = APP_NAME

    def __init__(
        self, argv: list[str], launch: Callable[[list[str]], None] = launch_detached
    ) -> None:
        # Must be set before AppPaths, which derives the data folder from it.
        QApplication.setApplicationName(self.APPLICATION_NAME)
        self._qt_app = QApplication(argv)
        self._qt_app.setWindowIcon(app_icon())
        self._qt_language = QtLanguage(self._qt_app)
        # Until the data says otherwise: the dialogs before it opens speak the system's.
        self._speak(system_language())
        self._argv = argv
        self._launch = launch
        self._set_taskbar_identity()
        # ``--smoke-test`` checks the built program, over a data folder of its own.
        self._smoke_test = SmokeTest() if SMOKE_TEST_FLAG in argv else None
        self._paths = self._smoke_test.paths if self._smoke_test else AppPaths.from_environment()
        self._window: MainWindow | None = None

    def run(self) -> int:
        """Runs the event loop and returns the process exit code.

        A Nodus already open over the same data is brought forward instead. The log and
        the error reporter cover the whole run, opening the data included, so nothing
        that fails, even before the window, goes unseen.
        """
        self._paths.ensure_data_dir()
        instance = SingleInstance(self._paths.data_dir)
        if not instance.acquire():
            return self._show_the_open_one(instance)
        run_log = RunLog(self._paths.logs_dir)
        run_log.start()
        reporter = ErrorReporter(visible_path(self._paths.logs_dir))
        if self._smoke_test is None:
            reporter.install()
        else:
            self._smoke_test.install()
        logger.info("Starting: %s", system_line())
        self._install_desktop_entry()
        try:
            code = self._open_and_run(reporter, instance)
        finally:
            logger.info("Closed")
            reporter.uninstall()
            run_log.stop()
            instance.release()
            if self._smoke_test is not None:
                self._smoke_test.close()
        if code == RESTART_EXIT_CODE:
            # Only now: the new one finds the data and the single instance free.
            self._launch(restart_command(self._argv))
            return 0
        return code

    def _install_desktop_entry(self) -> None:
        """The AppImage's icon in the dock and its entry in the menu; the smoke test,
        which touches nothing of the system, skips it."""
        entry = DesktopEntry.for_this_program()
        if entry is not None and self._smoke_test is None:
            entry.install()

    def _show_the_open_one(self, instance: SingleInstance) -> int:
        """This run ends here: the Nodus that is open comes to the front, or, if it does
        not answer, the user hears where to find it."""
        if sys.platform == "win32":
            # Windows lets only the foreground process hand the foreground over.
            ctypes.windll.user32.AllowSetForegroundWindow(ASFW_ANY)
        if instance.ask_first_to_show():
            return 0
        user_error(None, self.APPLICATION_NAME, _(ALREADY_OPEN), _(ALREADY_OPEN_HOW))
        return 1

    def _open_and_run(self, reporter: ErrorReporter, instance: SingleInstance) -> int:
        database = self._open_data()
        if database is None:
            return 1
        try:
            try:
                self._speak_the_data_language(database)
                self._open_window(Services.create(database, self._paths.backups_dir))
            except Exception as error:  # noqa: BLE001 - shown instead of a silent exit
                logger.error("Nodus could not start", exc_info=error)
                reporter.show(error)
                return 1
            assert self._window is not None
            instance.show_requested.connect(self._window.bring_to_front)
            return self._qt_app.exec()
        finally:
            database.close()

    def _speak(self, language: Language) -> None:
        install(language)
        self._qt_language.apply(language)

    def _speak_the_data_language(self, database: Database) -> None:
        """Nodus's language as the data keeps it, before anything is built: texts are
        translated when shown, and new data names its categories in it."""
        settings = SettingsService(database, SettingsRepository(database))
        language = settings.startup_language(database.created, system_language())
        logger.info("Language: %s", language.value)
        self._speak(language)

    def _open_data(self) -> Database | None:
        """The data, opened; or None, after telling the user why it could not be, in the
        way each failure needs."""
        try:
            return Database.open(self._paths.database_path)
        except NewerDatabaseError as error:
            logger.error("The data comes from a newer Nodus", exc_info=error)
            self._ask_to_update(error)
        except DamagedDatabaseError as error:
            logger.error("The data is damaged", exc_info=error)
            return self._recover(error)
        except MigrationError as error:
            logger.error("The data could not be updated", exc_info=error)
            UnexpectedErrorDialog(
                error,
                visible_path(self._paths.logs_dir),
                what=_(UPDATE_FAILED),
                how=_(UPDATE_FAILED_HOW),
            ).exec()
        except DatabaseError as error:
            logger.error("The data could not be opened", exc_info=error)
            self._tell_open_failed(error)
        return None

    def _ask_to_update(self, error: DatabaseError) -> None:
        dialog = UserErrorDialog(
            self.APPLICATION_NAME, _(NEWER_DATA), _(NEWER_DATA_HOW), str(error), action=_(DOWNLOAD)
        )
        if dialog.exec():
            open_url(DOWNLOAD_URL)

    def _recover(self, error: DatabaseError) -> Database | None:
        """Offers to bring the data back from the newest whole copy, and opens it."""
        recovery = DataRecovery(self._paths)
        copy = recovery.newest_copy()
        if not offer_recovery(copy, visible_path(self._paths.backups_dir), str(error)):
            return None
        assert copy is not None
        try:
            recovery.recover(copy, datetime.now())
            return Database.open(self._paths.database_path)
        except (OSError, DatabaseError) as again:
            logger.error("The data could not be recovered", exc_info=again)
            self._tell_open_failed(again)
            return None

    def _tell_open_failed(self, error: Exception) -> None:
        user_error(None, self.APPLICATION_NAME, _(OPEN_FAILED), _(OPEN_FAILED_HOW), str(error))

    def _open_window(self, services: Services) -> None:
        """Tidies the data up, opens the window and starts what runs behind it."""
        services.backups.create_if_due(date.today())
        if self._smoke_test is None:  # Windows' start-up entry is the real program's
            services.startup.repair()
        services.updates.clean()
        set_reduced_motion(services.settings.reduce_motion())
        theme_mode = ThemeMode.from_setting(services.settings.theme_preference())
        theme_manager = ThemeManager(self._qt_app, theme_mode)
        self._window = window = MainWindow(services, EventBus(), theme_manager)
        window.show()
        if self._smoke_test is not None:
            smoke_test, app = self._smoke_test, self._qt_app
            QTimer.singleShot(0, lambda: smoke_test.finish(app, window))
            return  # nothing from the internet, no dialogs nobody would answer
        window.check_for_updates()
        window.update_exchange_rate()
        # Once the window has painted, so the news appear over it, not before it.
        QTimer.singleShot(0, window.show_unseen_news)

    @staticmethod
    def _set_taskbar_identity() -> None:
        """Groups the windows under Nodus's own taskbar icon instead of Python's."""
        if sys.platform == "win32":
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
        else:
            QApplication.setDesktopFileName(DESKTOP_FILE_ID)


def main() -> int:
    return NodusApp(sys.argv).run()
