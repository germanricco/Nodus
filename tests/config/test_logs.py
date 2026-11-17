import faulthandler
import logging
from pathlib import Path

import pytest

from nodus.config.logs import (
    LOGGER_NAME,
    RunLog,
    code_path,
    describe,
    error_lines,
    scrub,
    system_line,
)


def raised(error: BaseException) -> BaseException:
    """``error`` with a traceback, as the hooks receive it."""
    try:
        raise error
    except BaseException as caught:  # noqa: BLE001
        return caught


@pytest.fixture
def run_log(tmp_path):
    log = RunLog(tmp_path / "logs")
    log.start()
    yield log
    log.stop()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("database is locked", "database is locked"),
        ("'Banco Galicia'", "'…'"),
        ('no such payee: "Coto"', 'no such payee: "…"'),
        ("la cuenta «Ahorro»", "la cuenta «…»"),
        ("amount 98765.43 too big", "amount … too big"),
        ("1.234.567,89", "…"),
        ("migration 12 failed", "migration 12 failed"),
        (r"C:\Users\Germán\AppData\Roaming\Nodus\nodus.db: locked", "….db: locked"),
        ("D:/Backups/Juan/nodus.db", "….db"),
        (
            r"C:\Users\Germán Ricco\Mis datos\Caja Galicia.db: not a database",
            "….db: not a database",
        ),
        (r"no access to 'E:\Pendrive Juan'", "no access to '…'"),
        ("C:\\Users\\Ana\\x.db\nnext line", "….db\nnext line"),
    ],
)
def test_scrub_hides_what_could_be_data(text, expected):
    assert scrub(text) == expected


def test_code_path_starts_at_the_package():
    assert code_path(r"C:\Users\Pc\Nodus\src\nodus\ui\app.py") == "nodus/ui/app.py"
    assert code_path(r"C:\Program Files\Nodus\_internal\nodus\models\money.py") == (
        "nodus/models/money.py"
    )
    assert code_path(r"C:\Python311\Lib\json\decoder.py") == "decoder.py"


def test_describe_names_the_kind_and_scrubs_the_message():
    assert describe(KeyError("Banco")) == "KeyError: '…'"
    assert describe(RuntimeError()) == "RuntimeError"


# The user's data reaches the code in variables, never written in it, as here.
NAME, AMOUNT = "Banco", 98765


def test_error_lines_tell_the_cause_first_and_where_each_step_was():
    def save(name, amount):
        try:
            {}[name]
        except KeyError as error:
            raise RuntimeError(f"could not save {amount}") from error

    error = raised(_call(lambda: save(NAME, AMOUNT)))
    lines = error_lines(error)

    assert lines[0] == "Traceback (most recent call last):"
    assert "KeyError: '…'" in lines
    assert "Which led to:" in lines
    assert lines[-1] == "RuntimeError: could not save …"
    assert any(line.startswith("  test_logs.py:") and "in save" in line for line in lines)
    assert not any("Banco" in line or "98765" in line for line in lines)


def _call(function):
    try:
        function()
    except BaseException as error:  # noqa: BLE001
        return error
    raise AssertionError("expected an error")


def test_system_line_says_the_version_and_the_system():
    line = system_line()

    assert line.startswith("Nodus ")
    assert "Python 3." in line
    assert line.endswith("desde el código")


def test_run_log_writes_to_the_log_file(run_log):
    logging.getLogger("nodus.test").info("Backup saved")

    text = run_log.log_file.read_text(encoding="utf-8")
    assert "INFO nodus.test: Backup saved" in text


def test_run_log_writes_scrubbed_tracebacks(run_log):
    error = raised(KeyError("Banco Galicia"))
    logging.getLogger("nodus.test").error("Unexpected error", exc_info=error)

    text = run_log.log_file.read_text(encoding="utf-8")
    assert "KeyError: '…'" in text
    assert "Galicia" not in text


def test_stop_leaves_logging_as_it_was(tmp_path):
    logger = logging.getLogger(LOGGER_NAME)
    handlers = list(logger.handlers)
    log = RunLog(tmp_path / "logs")
    log.start()
    assert faulthandler.is_enabled()
    log.stop()

    assert logger.handlers == handlers
    logging.getLogger("nodus.test").info("after stopping")
    assert "after stopping" not in log.log_file.read_text(encoding="utf-8")


def test_crash_log_is_where_faulthandler_writes(run_log):
    assert (run_log.logs_dir / "crash.log").exists()


def test_an_oversized_crash_log_starts_over(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "crash.log").write_text("x" * 2_000_000, encoding="utf-8")
    log = RunLog(logs)
    log.start()
    log.stop()

    assert Path(logs / "crash.log").stat().st_size == 0
