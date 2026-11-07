"""The changelog: what each version brought, read from ``CHANGELOG.md``.

The same file feeds the release notes (``scripts/release_notes.py``) and the news the
app shows after an update, so both always say the same thing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from importlib import resources
from pathlib import Path

from nodus.services.update_service import parse_version

CHANGELOG_NAME = "CHANGELOG.md"
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


def load_changelog() -> list[ChangelogEntry]:
    """The changelog that ships with this copy of Nodus.

    The installed program carries it inside the ``nodus`` package (see
    ``packaging/nodus.spec``); from the source code it is read at the repository root,
    where it lives. Missing, it is empty: news are never worth an error.
    """
    packaged = resources.files("nodus").joinpath(CHANGELOG_NAME)
    source = Path(__file__).resolve().parents[3] / CHANGELOG_NAME
    for candidate in (packaged, source):
        if candidate.is_file():
            try:
                return parse_changelog(candidate.read_text("utf-8"))
            except (OSError, ValueError):
                return []
    return []
