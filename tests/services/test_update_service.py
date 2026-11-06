import json

import pytest

from nodus.services.update_service import LATEST_RELEASE_API, Release, UpdateService, parse_version

RELEASE_PAGE = "https://github.com/germanricco/Nodus/releases/tag/v0.3.0"


def answer(tag: str) -> bytes:
    return json.dumps({"tag_name": tag, "html_url": RELEASE_PAGE}).encode()


@pytest.mark.parametrize(
    ("text", "expected"),
    [("v0.2.0", (0, 2, 0)), ("0.2.0", (0, 2, 0)), ("1.10", (1, 10))],
)
def test_parse_version(text, expected):
    assert parse_version(text) == expected


def test_versions_compare_as_numbers():
    assert parse_version("0.10.0") > parse_version("0.9.1")


def test_newer_release_is_reported():
    requested = []

    def fetch(url):
        requested.append(url)
        return answer("v0.3.0")

    assert UpdateService("0.2.0", fetch).check() == Release("0.3.0", RELEASE_PAGE)
    assert requested == [LATEST_RELEASE_API]


@pytest.mark.parametrize("tag", ["v0.2.0", "v0.1.1"])
def test_same_or_older_release_is_not_reported(tag):
    assert UpdateService("0.2.0", lambda _url: answer(tag)).check() is None


@pytest.mark.parametrize(
    "body",
    [b"not json", b"{}", b"[]", json.dumps({"tag_name": "beta", "html_url": "x"}).encode()],
)
def test_unexpected_answer_is_ignored(body):
    assert UpdateService("0.2.0", lambda _url: body).check() is None


def test_network_error_is_ignored():
    def fetch(_url):
        raise OSError("sin conexión")

    assert UpdateService("0.2.0", fetch).check() is None
