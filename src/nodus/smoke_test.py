"""``Nodus.exe --smoke-test``: the built program opens whole, or says what it lacks.

A piece PyInstaller leaves out (a Qt plugin, the changelog, a migration, a module
imported late) fails only in the built program, never in the tests, and the user
found it. The release workflow runs this on the program and on the installed copy
before publishing. It opens Nodus over a data folder of its own, asks nothing of the
internet or of Windows (the start-with-Windows entry is not touched), shows every page
and exits with 0, or 1 after logging each problem.
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
import threading
from pathlib import Path
from types import TracebackType

from PySide6.QtGui import QImageReader
from PySide6.QtWidgets import QApplication

from nodus import __version__
from nodus.config.paths import AppPaths
from nodus.i18n import Language, has_catalog
from nodus.services.app.changelog import load_changelog
from nodus.ui.navigation import PageId
from nodus.ui.qt_language import has_qt_texts
from nodus.ui.shell.main_window import MainWindow

FLAG = "--smoke-test"

logger = logging.getLogger(__name__)


def language_problems() -> list[str]:
    """The files a language needs that the built program lacks: Nodus's catalog for
    each language but Spanish, and Qt's own texts where Qt does not speak it already."""
    problems = []
    for language in Language:
        if not has_catalog(language):
            problems.append(f"the {language.value} catalog of Nodus's texts is missing")
        if not has_qt_texts(language):
            problems.append(f"Qt's {language.value} texts are missing")
    return problems


def window_problems(window: MainWindow) -> list[str]:
    """What the built program may lack, each told in one line; none when it is whole."""
    problems = []
    if not window.isVisible():
        problems.append("the window did not open")
    if b"svg" not in QImageReader.supportedImageFormats():
        problems.append("Qt's SVG plugin is missing: the icons do not show")
    problems.extend(language_problems())
    if not any(entry.version == __version__ for entry in load_changelog()):
        problems.append(f"the changelog has no section for {__version__}")
    for page_id in PageId:
        try:
            window.show_page(page_id)
        except Exception as error:  # noqa: BLE001 - every page is tried, each told
            logger.error("Page %s did not open", page_id.name, exc_info=error)
            problems.append(f"page {page_id.name} did not open: {error!r}")
    return problems


class SmokeTest:
    """One run of ``--smoke-test``: its data folder, the errors raised meanwhile and the
    exit code.

    The data folder is ``NODUS_DATA_DIR`` when set, so the workflow can print the log
    afterwards; otherwise a temporary one, removed at the end.
    """

    def __init__(self) -> None:
        override = os.environ.get(AppPaths.DATA_DIR_ENV_VAR)
        self._temporary = (
            None
            if override
            else tempfile.TemporaryDirectory(prefix="nodus-smoke-test-", ignore_cleanup_errors=True)
        )
        folder = override or self._temporary.name  # type: ignore[union-attr]
        self.paths = AppPaths(Path(folder))
        self.problems: list[str] = []
        self._previous: tuple | None = None

    def install(self) -> None:
        """Records the errors nothing caught, instead of showing them in a dialog that
        nobody would close."""
        self._previous = (sys.excepthook, threading.excepthook)
        sys.excepthook = self._on_error
        threading.excepthook = lambda args: self._on_error(
            args.exc_type, args.exc_value, args.exc_traceback
        )

    def _on_error(
        self, kind: type[BaseException], error: BaseException, trace: TracebackType | None
    ) -> None:
        logger.error("Unexpected error", exc_info=(kind, error, trace))
        self.problems.append(f"unexpected {kind.__name__}: {error}")

    def finish(self, app: QApplication, window: MainWindow) -> None:
        """Checks the open window and ends the run with its exit code."""
        self.problems.extend(window_problems(window))
        for problem in self.problems:
            logger.error("Smoke test: %s", problem)
        logger.info("Smoke test %s", "failed" if self.problems else "passed")
        app.exit(1 if self.problems else 0)

    def close(self) -> None:
        """Puts the error hooks back and removes the temporary data folder."""
        if self._previous is not None:
            sys.excepthook, threading.excepthook = self._previous  # type: ignore[assignment]
            self._previous = None
        if self._temporary is not None:
            self._temporary.cleanup()
