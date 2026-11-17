"""Downloads from the internet, shared by the services that consult an online source.

``urllib.request`` is imported where a download starts, not here: it takes a noticeable
part of the app's startup and is only needed once the window is open.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

TIMEOUT_SECONDS = 5
STREAM_TIMEOUT_SECONDS = 30
CHUNK_BYTES = 64 * 1024

# Downloads a URL and returns the body. Services receive one so tests can replace it and
# never touch the network.
Fetch = Callable[[str], bytes]
# Downloads a URL piece by piece, for files too large to hold in memory or to wait for
# without showing progress.
Stream = Callable[[str], Iterator[bytes]]


def downloader(user_agent: str, accept: str = "application/json") -> Fetch:
    """A ``Fetch`` that sends ``user_agent`` and gives up after a few seconds.

    Online sources are a convenience: a slow connection must never hold the app back.
    """

    def fetch(url: str) -> bytes:
        import urllib.request

        request = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": accept})
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.read()

    return fetch


def streamer(user_agent: str) -> Stream:
    """A ``Stream`` for large files: it waits up to ``STREAM_TIMEOUT_SECONDS`` for each
    chunk instead of for the whole download, so a slow but steady connection finishes."""

    def stream(url: str) -> Iterator[bytes]:
        import urllib.request

        request = urllib.request.Request(url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(request, timeout=STREAM_TIMEOUT_SECONDS) as response:
            while chunk := response.read(CHUNK_BYTES):
                yield chunk

    return stream
