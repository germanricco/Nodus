"""Checks GitHub for a newer published version of Nodus."""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

REPOSITORY = "germanricco/Nodus"
REPOSITORY_URL = f"https://github.com/{REPOSITORY}"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
_TIMEOUT_SECONDS = 5

# Downloads a URL and returns the body; replaced in tests so they never touch the network.
Fetch = Callable[[str], bytes]


@dataclass(frozen=True)
class Release:
    """A published version: its number ("0.2.0") and the page to download it from."""

    version: str
    url: str


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
        self._fetch = fetch or self._download

    def check(self) -> Release | None:
        """The latest release if it is newer than the running version, otherwise None.

        Any failure (no internet, GitHub down, an unexpected answer) also gives None:
        the check is a courtesy and must never get in the way of using the app.
        """
        try:
            data = json.loads(self._fetch(LATEST_RELEASE_API))
            latest = Release(data["tag_name"].removeprefix("v"), data["html_url"])
            is_newer = parse_version(latest.version) > parse_version(self.current_version)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return None
        return latest if is_newer else None

    def _download(self, url: str) -> bytes:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": f"Nodus/{self.current_version}",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            return response.read()
