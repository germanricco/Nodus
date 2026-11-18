from pathlib import Path

import pytest
from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QLineEdit

from nodus.i18n import Language
from nodus.ui.qt_language import QT_TEXTS, QtLanguage


def menu_texts() -> list[str]:
    field = QLineEdit()  # the menu lives as long as its field
    menu = field.createStandardContextMenu()
    return [action.text().split("	")[0].replace("&", "") for action in menu.actions()]


@pytest.fixture
def qt_language(qapp):
    """Leaves Qt as the other tests have it: no translator, and the system's locale."""
    language = QtLanguage(qapp)
    yield language
    if language._translator is not None:
        qapp.removeTranslator(language._translator)
    QLocale.setDefault(QLocale.system())


def test_in_spanish_the_menus_of_the_text_fields_speak_spanish(qt_language):
    """Qt names those itself, in English unless its Spanish texts are loaded."""
    qt_language.apply(Language.SPANISH)

    assert {"Copiar", "Pegar"} <= set(menu_texts())
    assert QLocale().standaloneMonthName(11) == "noviembre"


def test_in_english_qt_speaks_english_and_weeks_start_on_sunday(qt_language):
    qt_language.apply(Language.SPANISH)
    qt_language.apply(Language.ENGLISH)  # and the Spanish texts come off

    assert {"Copy", "Paste"} <= set(menu_texts())
    assert QLocale().standaloneMonthName(11) == "November"
    assert QLocale().firstDayOfWeek().name == "Sunday"


def test_the_installer_keeps_the_spanish_texts():
    """The installer leaves out Qt's translations (45 MB) but that one."""
    spec = (Path(__file__).parents[2] / "packaging" / "nodus.spec").read_text(encoding="utf-8")

    for name in QT_TEXTS.values():
        assert f"PySide6/translations/{name}.qm" in spec
