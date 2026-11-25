"""Writes ``latest.json``, the file from which Nodus learns of a new version, for the
release workflow to publish beside the installers (``release_manifest``).

It takes the notes from the tag's message, the same text the release page shows, and
measures the installers already built: if one is missing, it stops before anything is
published, since a release Nodus cannot install from would announce itself anyway.

Usage: python scripts/release_manifest.py 1.12.2 release-notes.md release
       (writes release/latest.json)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from nodus.services.external.release_manifest import MANIFEST_NAME, build_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", help="the version released, as in 1.12.2")
    parser.add_argument("notes", type=Path, help="the tag's message, the release notes")
    parser.add_argument("folder", type=Path, help="where the installers are")
    args = parser.parse_args(argv)
    try:
        manifest = build_manifest(args.version, args.notes.read_text(encoding="utf-8"), args.folder)
    except FileNotFoundError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    out = args.folder / MANIFEST_NAME
    out.write_text(manifest.to_json(), encoding="utf-8", newline="\n")
    print(f"{out}: {', '.join(manifest.installers)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
