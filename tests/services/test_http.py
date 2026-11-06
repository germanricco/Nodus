import urllib.request

from nodus.services.http import TIMEOUT_SECONDS, downloader


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
