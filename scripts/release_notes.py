"""Writes a version's release notes from its sections of CHANGELOG.md and CHANGELOG.en.md.

The file becomes the message of the annotated tag, which the release workflow publishes
as the notes of the GitHub release. Taking it from the changelogs keeps the release
page, the update notice and the news inside the app saying the same thing. The notes
carry both languages, the Spanish first; the update notice shows the part of the
language Nodus is in (``changelog.notes_in``).

Usage: .venv/Scripts/python scripts/release_notes.py 1.1.0 [--out notas.md]
       git tag -a v1.1.0 -F notas.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import ROOT

from nodus.i18n import Language
from nodus.models.version import parse_version
from nodus.services.app.changelog import (
    CHANGELOG_NAMES,
    ENGLISH_NOTES_MARK,
    NOTES_RULE,
    ChangelogEntry,
    parse_changelog,
)

FOOTERS = {
    Language.SPANISH: "Para actualizar, instala esta versión encima de la anterior: tus datos"
    " se conservan.",
    Language.ENGLISH: "To update, install this version over the previous one: your data is kept.",
}
# The first version with an English section; older ones have notes only in Spanish.
FIRST_ENGLISH = "1.10.0"


def release_notes(sections: dict[Language, ChangelogEntry]) -> str:
    """The tag message: a subject line with the version, then each language's section
    with its footer, the English after ``ENGLISH_NOTES_MARK``."""
    version = sections[Language.SPANISH].version
    parts = [f"{entry.body}\n\n{FOOTERS[language]}" for language, entry in sections.items()]
    separator = f"\n\n{NOTES_RULE}\n\n{ENGLISH_NOTES_MARK}\n\n"
    return f"Nodus {version}\n\n{separator.join(parts)}\n"


def find_entry(
    entries: list[ChangelogEntry], version: str, name: str = "CHANGELOG.md"
) -> ChangelogEntry:
    """The section of ``version`` in the changelog ``name``. Raises ValueError if it is
    missing or has no date yet."""
    version = version.removeprefix("v")
    for entry in entries:
        if entry.version == version:
            if entry.released is None:
                raise ValueError(f"The {version} section of {name} has no date.")
            return entry
    raise ValueError(f"{name} has no section for {version}.")


def find_sections(version: str, root: Path = ROOT) -> dict[Language, ChangelogEntry]:
    """The section of ``version`` in each language's changelog: Spanish always, English
    from ``FIRST_ENGLISH`` on."""
    languages = [Language.SPANISH]
    if parse_version(version.removeprefix("v")) >= parse_version(FIRST_ENGLISH):
        languages.append(Language.ENGLISH)
    sections = {}
    for language in languages:
        name = CHANGELOG_NAMES[language]
        entries = parse_changelog((root / name).read_text("utf-8"))
        sections[language] = find_entry(entries, version, name)
    return sections


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", help="the version to release, e.g. 1.1.0")
    parser.add_argument("--out", type=Path, default=Path("notas.md"), help="where to write")
    args = parser.parse_args(argv)
    try:
        sections = find_sections(args.version)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    args.out.write_text(release_notes(sections), "utf-8")
    print(f"Release notes for {sections[Language.SPANISH].version} written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
