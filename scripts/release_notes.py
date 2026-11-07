"""Writes a version's release notes from its section of CHANGELOG.md.

The file becomes the message of the annotated tag, which the release workflow publishes
as the notes of the GitHub release. Taking it from the changelog keeps the release page,
the update notice and the news inside the app saying the same thing.

Usage: .venv/Scripts/python scripts/release_notes.py 1.1.0 [--out notas.md]
       git tag -a v1.1.0 -F notas.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from nodus.services.changelog import ChangelogEntry, parse_changelog

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"
FOOTER = "Para actualizar, instala esta versión encima de la anterior: tus datos se conservan."


def release_notes(entry: ChangelogEntry) -> str:
    """The tag message: a subject line with the version, the section and the footer."""
    return f"Nodus {entry.version}\n\n{entry.body}\n\n{FOOTER}\n"


def find_entry(entries: list[ChangelogEntry], version: str) -> ChangelogEntry:
    """The section of ``version``. Raises ValueError if it is missing or has no date yet."""
    version = version.removeprefix("v")
    for entry in entries:
        if entry.version == version:
            if entry.released is None:
                raise ValueError(f"The {version} section of CHANGELOG.md has no date.")
            return entry
    raise ValueError(f"CHANGELOG.md has no section for {version}.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", help="the version to release, e.g. 1.1.0")
    parser.add_argument("--out", type=Path, default=Path("notas.md"), help="where to write")
    args = parser.parse_args(argv)
    try:
        entry = find_entry(parse_changelog(CHANGELOG.read_text("utf-8")), args.version)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    args.out.write_text(release_notes(entry), "utf-8")
    print(f"Release notes for {entry.version} written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
