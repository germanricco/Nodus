from pathlib import Path
from urllib.parse import parse_qs, urlparse

from nodus.links import MAX_URL_LENGTH
from nodus.ui.text.error_report import ASK, MOST_STEPS, error_report, report_url

# The user's data reaches the code in variables, and Nodus's messages quote names in «».
NAME, AMOUNT = "Banco Galicia", "98765.43"


def failure(depth: int = 3, message: str = "") -> BaseException:
    """A ``ValueError`` raised ``depth`` calls deep, with ``message``."""

    def step(level: int) -> None:
        if level == 0:
            raise ValueError(message or f"could not save «{NAME}» with {AMOUNT}")
        step(level - 1)

    try:
        step(depth)
    except ValueError as error:
        return error
    raise AssertionError


def detail_of(url: str) -> str:
    return parse_qs(urlparse(url).query)["entry.1232171367"][0]


def test_the_report_asks_what_the_user_was_doing_first():
    assert error_report(failure()).startswith(ASK)


def test_the_report_says_the_error_and_its_last_steps_first():
    lines = error_report(failure()).splitlines()

    assert "Error: ValueError: could not save «…» with …" in lines
    steps = [line for line in lines if line.startswith("test_error_report.py:")]
    assert steps[0].endswith("en step")
    assert lines[-1].startswith("Nodus ")


def test_the_report_has_no_user_data_nor_user_folders():
    report = error_report(failure(message=rf"C:\Users\Germán\nodus.db: «{NAME}» {AMOUNT}"))

    assert "Galicia" not in report
    assert "98765" not in report
    assert "Germán" not in report
    assert str(Path.home()) not in report


def test_the_report_keeps_at_most_the_last_steps():
    lines = error_report(failure(depth=30)).splitlines()

    assert len([line for line in lines if " en step" in line]) == MOST_STEPS


def test_the_link_fits_even_with_a_long_error():
    url = report_url(failure(depth=60, message="x" * 5000))

    assert len(url) <= MAX_URL_LENGTH
    assert "ValueError" in detail_of(url)


def test_the_link_carries_the_report():
    error = failure()

    assert detail_of(report_url(error)) == error_report(error)
