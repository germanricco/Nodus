import logging
from pathlib import Path

import pytest
import translations
from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo

from nodus import i18n
from nodus.i18n import N_, Language, _, ngettext, pgettext


@pytest.fixture
def sample_catalog(tmp_path, monkeypatch) -> Path:
    """An English catalog with a few texts, in place of the real one."""
    catalog = Catalog(locale="en")
    catalog.add("Guardar", "Save")
    catalog.add(("{n} cuota", "{n} cuotas"), ("{n} installment", "{n} installments"))
    catalog.add("Nueva", "New", context="goal")
    folder = tmp_path / "en" / "LC_MESSAGES"
    folder.mkdir(parents=True)
    with (folder / "nodus.mo").open("wb") as file:
        write_mo(file, catalog)
    monkeypatch.setattr(i18n, "LOCALE_DIR", tmp_path)
    yield tmp_path
    i18n.install(Language.SPANISH)


def test_spanish_is_the_source_and_needs_no_catalog():
    i18n.install(Language.SPANISH)

    assert _("Guardar") == "Guardar"
    assert ngettext("{n} cuota", "{n} cuotas", 1) == "{n} cuota"
    assert ngettext("{n} cuota", "{n} cuotas", 3) == "{n} cuotas"
    assert pgettext("goal", "Nueva") == "Nueva"


def test_english_translates_texts_plurals_and_texts_with_context(sample_catalog):
    i18n.install(Language.ENGLISH)

    assert i18n.current_language() is Language.ENGLISH
    assert _("Guardar") == "Save"
    assert ngettext("{n} cuota", "{n} cuotas", 1).format(n=1) == "1 installment"
    assert ngettext("{n} cuota", "{n} cuotas", 0).format(n=0) == "0 installments"
    assert pgettext("goal", "Nueva") == "New"
    assert _("Un texto sin traducir") == "Un texto sin traducir"  # rather than nothing


def test_back_in_spanish_the_source_texts_return(sample_catalog):
    i18n.install(Language.ENGLISH)
    i18n.install(Language.SPANISH)

    assert _("Guardar") == "Guardar"


def test_without_its_catalog_nodus_stays_in_spanish_and_logs_why(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(i18n, "LOCALE_DIR", tmp_path)
    try:
        with caplog.at_level(logging.WARNING):
            i18n.install(Language.ENGLISH)
        assert _("Guardar") == "Guardar"
        assert "No en catalog" in caplog.text
    finally:
        i18n.install(Language.SPANISH)


def test_the_real_english_catalog_loads(english, caplog):
    """The tests compile it before they start (``tests/conftest.py``)."""
    assert i18n.current_language() is Language.ENGLISH
    assert "catalog" not in caplog.text


def test_a_marked_text_is_kept_as_written_until_shown():
    assert N_("Guardar") == "Guardar"


def test_each_language_is_named_in_itself():
    assert [language.native_name for language in Language] == ["Español", "English"]


# scripts/translations.py


@pytest.fixture
def code(tmp_path, monkeypatch) -> Path:
    """A package of code to extract from, in place of ``src/nodus``."""
    monkeypatch.setattr(translations, "PACKAGE", tmp_path)
    return tmp_path


def test_extracting_finds_every_kind_of_mark(code):
    (code / "page.py").write_text(
        "from nodus.i18n import N_, _, ngettext, pgettext\n"
        "TITLE = N_('Metas')\n"
        "def texts(n):\n"
        "    plural = ngettext('{n} cuota', '{n} cuotas', n)\n"
        "    return _('Guardar'), plural, pgettext('goal', 'Nueva')\n",
        encoding="utf-8",
    )

    found = {(message.context, message.id) for message in translations.extracted() if message.id}

    assert found == {
        (None, "Metas"),
        (None, "Guardar"),
        (None, ("{n} cuota", "{n} cuotas")),
        ("goal", "Nueva"),
    }


def catalog_with(*messages: tuple) -> Catalog:
    catalog = Catalog(locale="en")
    for message_id, string, *flags in messages:
        catalog.add(message_id, string, flags=flags)
    return catalog


def test_a_complete_catalog_has_no_problems():
    template = catalog_with(("Vence hoy", ""))
    catalog = catalog_with(("Vence hoy", "Due today"))

    assert translations.problems(catalog, template) == []


def test_the_problems_of_a_catalog_are_named():
    template = catalog_with(("Vence hoy", ""), ("Nuevo en el código", ""))
    catalog = catalog_with(
        ("Vence hoy", ""),
        ("Vencido hace {days} días", "Overdue by {dias} days"),
        ("Guardar", "Save", "fuzzy"),
    )

    found = translations.problems(catalog, template)

    assert found == [
        "falta en el catálogo (extract): 'Nuevo en el código'",
        "sin traducir: 'Vence hoy'",
        "marcadores distintos: 'Vencido hace {days} días' → 'Overdue by {dias} days'",
        "dudosa (fuzzy): 'Guardar'",
    ]


def test_the_singular_of_a_plural_may_leave_the_number_out():
    template = Catalog(locale="en")
    catalog = Catalog(locale="en")
    catalog.add(("{n} cuota", "{n} cuotas"), ("one installment", "{n} installments"))
    catalog.add(("{n} meta", "{n} metas"), ("{n} goal", "goals"))
    catalog.add(("{n} día", "{n} días"), ("{n} day", "{n} days in {month}"))

    assert translations.problems(catalog, template) == [
        "marcadores distintos: '{n} meta' → 'goals'",
        "marcadores distintos: '{n} día' → '{n} days in {month}'",
    ]


def test_literal_braces_are_not_placeholders():
    assert translations.placeholders("{{literal}} y {name} con {amount:>8}") == {"name", "amount"}


def test_every_text_the_code_marks_has_its_translation():
    """``scripts/translations.py extract`` brings new texts into the catalog, and each
    needs its translation before the version is published."""
    assert translations.check() == []
