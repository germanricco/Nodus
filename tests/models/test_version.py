import pytest

from nodus.models.version import parse_version


@pytest.mark.parametrize(
    ("text", "expected"),
    [("v0.2.0", (0, 2, 0)), ("0.2.0", (0, 2, 0)), ("1.10", (1, 10))],
)
def test_parse_version(text, expected):
    assert parse_version(text) == expected


def test_versions_compare_as_numbers():
    assert parse_version("0.10.0") > parse_version("0.9.1")
