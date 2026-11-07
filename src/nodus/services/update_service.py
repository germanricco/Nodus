"""Checks GitHub for a newer published version of Nodus."""

from __future__ import annotations

import json
from dataclasses import dataclass

from nodus.links import REPOSITORY
from nodus.services.http import Fetch, downloader

LATEST_RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
GITHUB_JSON = "application/vnd.github+json"


@dataclass(frozen=True)
class Release:
    """A published version: its number ("0.2.0"), the page to download it from and its
    release notes in Markdown (what it brings)."""

    version: str
    url: str
    notes: str = ""


def parse_version(text: str) -> tuple[int, ...]:
    """ "v0.2.0" or "0.2.0" as (0, 2, 0), so versions compare as numbers ("0.10" > "0.9").

    Raises ValueError if ``text`` is not dot-separated numbers.
    """
    return tuple(int(part) for part in text.strip().removeprefix("v").split("."))


class UpdateService:
    """Asks GitHub for the latest release and compares it with the running version.

    Only the version number is requested; nothing about the user or their data is sent.
    """

    def __init__(self, current_version: str, fetch: Fetch | None = None) -> None:
        self.current_version = current_version
        self._fetch = fetch or downloader(f"Nodus/{current_version}", GITHUB_JSON)

    def check(self) -> Release | None:
        """The latest release if it is newer than the running version, otherwise None.

        Any failure (no internet, GitHub down, an unexpected answer) also gives None:
        the check is a courtesy and must never get in the way of using the app.
        """
        try:
            data = json.loads(self._fetch(LATEST_RELEASE_API))
            version = data["tag_name"].removeprefix("v")
            # The notes open with the tag's subject line, which repeats the version.
            notes = (data.get("body") or "").strip().removeprefix(f"Nodus {version}").strip()
            latest = Release(version, data["html_url"], notes)
            is_newer = parse_version(latest.version) > parse_version(self.current_version)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return None
        return latest if is_newer else None
