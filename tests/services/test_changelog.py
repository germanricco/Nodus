from datetime import date
from pathlib import Path

import pytest
import release_notes

from nodus import __version__
from nodus.services.changelog import (
    ChangelogEntry,
    entries_between,
    load_changelog,
    parse_changelog,
)
from nodus.services.update_service import parse_version

SAMPLE = """# Novedades de Nodus

Una introducción que no es de ninguna versión.

## 1.1.0

- Algo nuevo.

## 1.0.1 — 2026-11-06

Un resumen.

- Un arreglo.

## 1.0.0 — 2026-11-06

- La estable.
"""


def entry(version: str) -> ChangelogEntry:
    return ChangelogEntry(version, None, "")


def test_parse_reads_each_section_with_its_date_and_body():
    entries = parse_changelog(SAMPLE)

    assert [e.version for e in entries] == ["1.1.0", "1.0.1", "1.0.0"]
    assert entries[0].released is None
    assert entries[1].released == date(2026, 11, 6)
    assert entries[1].body == "Un resumen.\n\n- Un arreglo."


def test_parse_rejects_a_heading_that_is_not_a_version():
    with pytest.raises(ValueError):
        parse_changelog("## Próximamente\n\n- Algo.")


def test_entries_between_excludes_the_lower_end_and_includes_the_upper():
    entries = [entry("1.2.0"), entry("1.1.0"), entry("1.0.1"), entry("1.0.0")]

    found = entries_between(entries, "1.0.0", "1.1.0")

    assert [e.version for e in found] == ["1.1.0", "1.0.1"]


def test_the_real_changelog_is_valid_and_covers_this_version():
    entries = load_changelog()
    versions = [parse_version(e.version) for e in entries]

    assert versions == sorted(versions, reverse=True)
    assert len(set(versions)) == len(versions)
    assert __version__ in {e.version for e in entries}
    assert all(e.body for e in entries)


def test_release_notes_have_the_subject_line_the_section_and_the_footer(tmp_path: Path):
    out = tmp_path / "notas.md"

    assert release_notes.main(["v1.0.1", "--out", str(out)]) == 0

    notes = out.read_text("utf-8")
    assert notes.startswith("Nodus 1.0.1\n\n- Los filtros de Transacciones")
    assert notes.rstrip().endswith(release_notes.FOOTER)


def test_release_notes_refuse_a_missing_or_undated_section():
    entries = parse_changelog(SAMPLE)

    with pytest.raises(ValueError, match="no section"):
        release_notes.find_entry(entries, "9.9.9")
    with pytest.raises(ValueError, match="no date"):
        release_notes.find_entry(entries, "1.1.0")
