"""Downloads from the internet, shared by the services that consult an online source."""

from __future__ import annotations

import urllib.request
from collections.abc import Callable

TIMEOUT_SECONDS = 5

# Downloads a URL and returns the body. Services receive one so tests can replace it and
# never touch the network.
Fetch = Callable[[str], bytes]


def downloader(user_agent: str, accept: str = "application/json") -> Fetch:
    """A ``Fetch`` that sends ``user_agent`` and gives up after a few seconds.

    Online sources are a convenience: a slow connection must never hold the app back.
    """

    def fetch(url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": accept})
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.read()

    return fetch
