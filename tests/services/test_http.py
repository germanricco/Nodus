import urllib.request

from nodus.services.http import (
    CHUNK_BYTES,
    STREAM_TIMEOUT_SECONDS,
    TIMEOUT_SECONDS,
    downloader,
    streamer,
)


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._body


def test_downloader_sends_headers_and_timeout(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["request"], seen["timeout"] = request, timeout
        return FakeResponse(b"{}")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    body = downloader("Nodus/1.0", accept="text/plain")("https://example.com/x")

    assert body == b"{}"
    assert seen["request"].full_url == "https://example.com/x"
    assert seen["request"].get_header("User-agent") == "Nodus/1.0"
    assert seen["request"].get_header("Accept") == "text/plain"
    assert seen["timeout"] == TIMEOUT_SECONDS


class FakeStreamResponse(FakeResponse):
    def read(self, size: int = -1) -> bytes:
        piece, self._body = self._body[:size], self._body[size:]
        return piece


def test_streamer_reads_in_chunks_with_a_per_chunk_timeout(monkeypatch):
    seen = {}
    response = FakeStreamResponse(b"x" * (CHUNK_BYTES * 2 + 10))

    def fake_urlopen(request, timeout):
        seen["request"], seen["timeout"] = request, timeout
        return response

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    pieces = list(streamer("Nodus/1.0")("https://example.com/setup.exe"))

    assert [len(piece) for piece in pieces] == [CHUNK_BYTES, CHUNK_BYTES, 10]
    assert seen["timeout"] == STREAM_TIMEOUT_SECONDS
    assert seen["request"].get_header("User-agent") == "Nodus/1.0"
