"""The language Nodus speaks: the one place every text the user reads is translated.

Spanish is the source language: the texts are written in Spanish in the code, marked
with ``_()``, and Spanish needs no catalog. English lives in
``locale/en/LC_MESSAGES/nodus.mo``, compiled from the ``.po`` by
``scripts/translations.py``. ``gettext`` and not Qt's ``tr()``, because models and
services have texts the user reads and cannot import Qt.

A text is translated when it is used, never when its module is imported: Nodus imports
its whole interface before it opens the database, where the chosen language is saved.
A table of texts at module level holds ``N_("…")``, which only marks the text for the
catalog, and whoever shows it calls ``_()`` on it then.
"""

from __future__ import annotations

import gettext
import logging
from enum import Enum
from importlib import resources

logger = logging.getLogger(__name__)

DOMAIN = "nodus"
LOCALE_DIR = resources.files("nodus").joinpath("locale")


class Language(Enum):
    """A language Nodus can be used in; its value is the catalog's language code."""

    SPANISH = "es"
    ENGLISH = "en"

    @property
    def native_name(self) -> str:
        """The language's name in itself, so it can be found by someone who does not
        read the language Nodus is in."""
        return _NATIVE_NAMES[self]


_NATIVE_NAMES = {Language.SPANISH: "Español", Language.ENGLISH: "English"}
SOURCE_LANGUAGE = Language.SPANISH

_language = SOURCE_LANGUAGE
_translations: gettext.NullTranslations = gettext.NullTranslations()


def install(language: Language) -> None:
    """Makes ``language`` the one every later ``_()`` translates into. Without its
    catalog Nodus keeps working, in the source language, and says so in the log."""
    global _language, _translations
    _language = language
    _translations = gettext.NullTranslations()
    if language is SOURCE_LANGUAGE:
        return
    try:
        _translations = gettext.translation(
            DOMAIN, localedir=str(LOCALE_DIR), languages=[language.value]
        )
    except FileNotFoundError:
        logger.warning("No %s catalog found: texts stay in Spanish", language.value)


def language_from_code(code: str | None) -> Language | None:
    """The language saved as ``code`` ("es", "en"), or None if unknown or missing."""
    try:
        return Language(code)
    except ValueError:
        return None


def has_catalog(language: Language) -> bool:
    """Whether ``language`` can be shown: the source always, any other with its catalog."""
    if language is SOURCE_LANGUAGE:
        return True
    return LOCALE_DIR.joinpath(language.value, "LC_MESSAGES", f"{DOMAIN}.mo").is_file()


def current_language() -> Language:
    return _language


def _(message: str) -> str:
    """``message``, written in Spanish, in the current language."""
    return _translations.gettext(message)


def ngettext(singular: str, plural: str, count: int) -> str:
    """The form that agrees with ``count``, in the current language: each language has
    its own rules for plurals, so the code never picks the form itself."""
    return _translations.ngettext(singular, plural, count)


def pgettext(context: str, message: str) -> str:
    """``message`` where the same short Spanish text needs different words in another
    language depending on where it is shown; ``context`` tells the places apart."""
    return _translations.pgettext(context, message)


def quoted(name: str) -> str:
    """A name the user gave, set apart in a sentence the way the language does it:
    «Sueldo» in Spanish, “Salary” in English."""
    return _("«{name}»").format(name=name)


def N_(message: str) -> str:  # noqa: N802 (the name gettext tools look for)
    """Marks ``message`` for the catalog without translating it yet: for texts kept at
    module level, which are translated with ``_()`` where they are shown."""
    return message
