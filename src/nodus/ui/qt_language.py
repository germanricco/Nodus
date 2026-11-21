"""Qt's side of the language: the texts Qt writes itself and the locale its widgets use.

``nodus.i18n`` translates Nodus's own texts. Qt has others: the right-click menu of a
text field («Copiar», «Pegar») and the names of months and days in the calendar under
a date field. They follow the same language through this class.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtWidgets import QApplication

from nodus.i18n import Language

logger = logging.getLogger(__name__)

# The only Qt translation the installer keeps (packaging/nodus.spec): Qt's own texts are
# already in English.
QT_TEXTS = {Language.SPANISH: "qtbase_es"}
LOCALES = {
    Language.SPANISH: QLocale(QLocale.Language.Spanish, QLocale.Country.Argentina),
    Language.ENGLISH: QLocale(QLocale.Language.English, QLocale.Country.UnitedStates),
}


def _loaded_texts(language: Language, app: QApplication | None = None) -> QTranslator | None:
    """Qt's own texts in ``language``, or None when Qt needs none or lacks the file."""
    name = QT_TEXTS.get(language)
    if name is None:
        return None
    translator = QTranslator(app)
    folder = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    return translator if translator.load(name, folder) else None


def has_qt_texts(language: Language) -> bool:
    """Whether Qt can speak ``language``: in English it needs no file of its own."""
    return language not in QT_TEXTS or _loaded_texts(language) is not None


def system_language() -> Language:
    """Spanish if the system speaks Spanish; English for any other language, since it is
    the one more people read."""
    if QLocale.system().language() is QLocale.Language.Spanish:
        return Language.SPANISH
    return Language.ENGLISH


class QtLanguage:
    """Puts Qt in a language, and keeps its translator alive while it is in use."""

    def __init__(self, app: QApplication) -> None:
        self._app = app
        self._translator: QTranslator | None = None

    def apply(self, language: Language) -> None:
        """Qt's texts and locale in ``language``. Without Qt's file for it, Nodus still
        opens, with Qt's few texts in English."""
        QLocale.setDefault(LOCALES[language])
        if self._translator is not None:
            self._app.removeTranslator(self._translator)
            self._translator = None
        translator = _loaded_texts(language, self._app)
        if translator is None:
            if language in QT_TEXTS:
                logger.warning("Qt's %s texts not found", language.value)
            return
        self._app.installTranslator(translator)
        self._translator = translator
