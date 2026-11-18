"""The changelog: what each version brought, read from ``CHANGELOG.md`` and, in English,
``CHANGELOG.en.md``.

The same files feed the release notes (``scripts/release_notes.py``) and the news the
app shows after an update, so both always say the same thing. A release's notes carry
both languages, the Spanish first; ``notes_in`` keeps the part of one language.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path

from nodus.i18n import SOURCE_LANGUAGE, Language, current_language
from nodus.models.version import parse_version

CHANGELOG_NAMES = {Language.SPANISH: "CHANGELOG.md", Language.ENGLISH: "CHANGELOG.en.md"}
# Where the English half of a release's notes starts, after a rule that sets it apart
# on the release page, where the mark itself does not show.
ENGLISH_NOTES_MARK = "<!-- en -->"
NOTES_RULE = "---"
# "## 1.1.0 — 2026-11-07"; the date is optional while a version is being written.
_HEADING = re.compile(r"^## (\d+(?:\.\d+)*)(?:\s+—\s+(\d{4}-\d{2}-\d{2}))?\s*$")


@dataclass(frozen=True)
class ChangelogEntry:
    """One version's section: its number, release date and Markdown body."""

    version: str
    released: date | None
    body: str


def parse_changelog(text: str) -> list[ChangelogEntry]:
    """The sections of ``text``, in file order (newest first); the intro is skipped."""
    entries: list[ChangelogEntry] = []
    heading: re.Match[str] | None = None
    lines: list[str] = []

    def close() -> None:
        if heading is not None:
            released = date.fromisoformat(heading[2]) if heading[2] else None
            entries.append(ChangelogEntry(heading[1], released, "\n".join(lines).strip()))

    for line in text.splitlines():
        match = _HEADING.match(line)
        if match:
            close()
            heading, lines = match, []
        elif line.startswith("## "):
            raise ValueError(f"Unexpected changelog heading: {line!r}")
        else:
            lines.append(line)
    close()
    return entries


def entries_between(entries: list[ChangelogEntry], after: str, up_to: str) -> list[ChangelogEntry]:
    """The entries newer than ``after`` and not newer than ``up_to``, newest first."""
    low, high = parse_version(after), parse_version(up_to)
    return [e for e in entries if low < parse_version(e.version) <= high]


def notes_in(language: Language, notes: str) -> str:
    """The part of a release's ``notes`` in ``language``: the Spanish comes before
    ``ENGLISH_NOTES_MARK`` and the English after it. Notes without the mark, from the
    releases before Nodus spoke English, are whole in any language."""
    spanish, mark, english = notes.partition(ENGLISH_NOTES_MARK)
    if not mark:
        return notes
    if language is Language.ENGLISH:
        return english.strip()
    return spanish.strip().removesuffix(NOTES_RULE).strip()


def load_changelog(language: Language | None = None) -> list[ChangelogEntry]:
    """The changelog that ships with this copy of Nodus, in ``language`` (by default the
    one Nodus is in); the Spanish one if that language has none.

    The installed program carries the files inside the ``nodus`` package (see
    ``packaging/nodus.spec``); from the source code they are read at the repository
    root, where they live. Missing, the changelog is empty: news are never worth an
    error.
    """
    files = changelog_files()
    for candidate in [*files[language or current_language()], *files[SOURCE_LANGUAGE]]:
        if candidate.is_file():
            try:
                return parse_changelog(candidate.read_text("utf-8"))
            except (OSError, ValueError):
                return []
    return []


def changelog_files() -> dict[Language, list[Traversable | Path]]:
    """Where each language's changelog may be: inside the package, where the installed
    program carries it, then at the repository root, where the source code has it."""
    return {
        language: [
            resources.files("nodus").joinpath(name),
            Path(__file__).resolve().parents[4] / name,
        ]
        for language, name in CHANGELOG_NAMES.items()
    }
