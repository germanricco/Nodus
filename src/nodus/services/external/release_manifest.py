"""``latest.json``: the file each release publishes beside its installers, from which Nodus
learns that there is a new version.

Nodus downloads it from ``releases/latest/download/latest.json``, a plain download from
GitHub's release page, and not from GitHub's API: the API answers only 60 requests an
hour to each connection without an account, and a connection shared by many people uses
them up, so the update notice never came. The file carries all the check needs, the
version, its notes and the size and SHA-256 of each installer, to check the download
against. The release workflow writes it (``scripts/release_manifest.py``) and Nodus reads
it here, so its format lives in one place.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

MANIFEST_NAME = "latest.json"
# Raised if the file ever changes in a way an older Nodus could not read.
FORMAT = 1
_CHUNK_BYTES = 1024 * 1024


def installer_names(version: str) -> dict[str, str]:
    """The file that installs ``version`` on each system, by ``sys.platform``, as
    ``scripts/build.py`` and ``packaging/nodus.iss`` name it."""
    return {
        "win32": f"Nodus-Setup-{version}.exe",
        "linux": f"Nodus-{version}-x86_64.AppImage",
    }


@dataclass(frozen=True)
class InstallerFile:
    """An installer attached to the release: its size and SHA-256, in hexadecimal."""

    size: int
    sha256: str


@dataclass(frozen=True)
class ReleaseManifest:
    """What ``latest.json`` says: the release's ``version`` ("1.12.2"), its ``notes`` in
    Markdown (the tag's text, in both languages, as on the release page) and its
    ``installers`` by file name."""

    version: str
    notes: str
    installers: dict[str, InstallerFile]

    def to_json(self) -> str:
        installers = {
            name: {"size": file.size, "sha256": file.sha256}
            for name, file in self.installers.items()
        }
        data = {
            "format": FORMAT,
            "version": self.version,
            "notes": self.notes,
            "installers": installers,
        }
        return json.dumps(data, ensure_ascii=False, indent=2) + "\n"

    @classmethod
    def from_json(cls, data: bytes) -> ReleaseManifest:
        """Reads ``data``; raises ``ValueError`` if it is not a manifest Nodus can read."""
        try:
            parsed = json.loads(data)
            if parsed["format"] != FORMAT:
                raise ValueError(f"manifest format {parsed['format']!r}")
            installers = {
                str(name): InstallerFile(int(file["size"]), str(file["sha256"]))
                for name, file in parsed["installers"].items()
            }
            version, notes = parsed["version"], parsed["notes"]
        except (KeyError, TypeError, AttributeError) as error:
            raise ValueError(f"incomplete manifest: {error!r}") from error
        if not isinstance(version, str) or not isinstance(notes, str):
            raise ValueError("manifest version or notes are not text")
        return cls(version, notes, installers)


def build_manifest(version: str, notes: str, folder: Path) -> ReleaseManifest:
    """The manifest of ``version``, measuring its installers in ``folder``: every system's
    must be there. Raises ``FileNotFoundError`` naming the one missing."""
    installers = {}
    for name in installer_names(version).values():
        path = folder / name
        if not path.is_file():
            raise FileNotFoundError(f"{name} is not in {folder}")
        installers[name] = InstallerFile(path.stat().st_size, _sha256(path))
    return ReleaseManifest(version, notes, installers)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()
