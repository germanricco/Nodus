"""Nodus's log: a few small files next to the data that say what happened, so an error
can be found after the fact, even in the installed program, which has no console.

Lines name events and kinds of errors, never amounts, names or notes: the user may
send the log to report a problem. Error messages can carry such data (a ``KeyError``
names the key), so ``scrub`` covers them before they are written or reported. It finds
names because they come quoted: Python's errors use ``repr``, and Nodus's messages «».
"""

from __future__ import annotations

import contextlib
import faulthandler
import logging
import platform
import re
import sys
import traceback
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path, PureWindowsPath
from typing import TextIO

from nodus import __version__, is_installed

LOGGER_NAME = "nodus"  # every module logs under it, with logging.getLogger(__name__)
LOG_FILENAME = "nodus.log"
CRASH_FILENAME = "crash.log"  # what faulthandler writes when the process dies at once
MAX_BYTES = 1_000_000
KEPT_FILES = 3  # besides the current one

HIDDEN = "…"
# Up to the ": " that follows a path in a message, a quote or the end of the line: folders
# and file names may have spaces, and both are the user's.
# A drive letter on its own, so the "s:/" of a web address is not taken for one.
_WINDOWS_PATH = re.compile(r"(?<!\w)[A-Za-z]:[\\/].*?(?=: |['\"«»]|$)", re.MULTILINE)
# The same on Linux: "~/…", or "/home/ana/…" with two parts at least, after a space or a
# bracket, so that "and/or", "km/h" and the "//" of a link stay as they are.
_POSIX_PATH = re.compile(r"(?<![^\s(\[=])(?:~/|/[^\s/'\"«»]+/).*?(?=: |['\"«»]|$)", re.MULTILINE)
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"|«[^»]*»")
# Three characters or more: amounts, ids and dates; a one or two digit count stays.
_LONG_NUMBER = re.compile(r"\d[\d.,]{2,}")


def system_line() -> str:
    """ "Nodus 1.9.0 · Windows 10.0.26300 · Python 3.11.9 · instalado": what an error
    report needs to know about where it happened."""
    where = "instalado" if is_installed() else "desde el código"
    return (
        f"Nodus {__version__} · {platform.system()} {platform.version()}"
        f" · Python {platform.python_version()} · {where}"
    )


def scrub(text: str) -> str:
    """``text`` without what could be the user's data: quoted values, long numbers and
    paths, of which only the kind of file stays ("….db")."""
    for path in (_WINDOWS_PATH, _POSIX_PATH):
        text = path.sub(lambda m: HIDDEN + Path(m.group()).suffix, text)
    text = _QUOTED.sub(lambda m: f"{m.group()[0]}{HIDDEN}{m.group()[-1]}", text)
    return _LONG_NUMBER.sub(HIDDEN, text)


@dataclass(frozen=True)
class Frame:
    """One step of a traceback: where in the code, and in which function."""

    path: str  # "nodus/ui/dialogs/transaction_dialog.py", or a file name outside Nodus
    line: int
    function: str
    code: str


def code_path(filename: str) -> str:
    """The path of a source file from the ``nodus`` package on, the same in any install
    and without the user's folders; for anything else, its file name. Read as a Windows
    path, which also splits on "/", so it works with the paths of either system."""
    parts = PureWindowsPath(filename).parts
    if "nodus" not in parts:
        return PureWindowsPath(filename).name
    start = len(parts) - 1 - parts[::-1].index("nodus")
    return "/".join(parts[start:])


def frames(error: BaseException) -> list[Frame]:
    """The steps that led to ``error``, the outermost first, as Python prints them."""
    return [
        Frame(code_path(f.filename), f.lineno or 0, f.name, (f.line or "").strip())
        for f in traceback.extract_tb(error.__traceback__)
    ]


def describe(error: BaseException) -> str:
    """ "KeyError: '…'": the kind of error and its message, scrubbed."""
    message = scrub(str(error))
    return f"{type(error).__name__}: {message}" if message else type(error).__name__


def error_lines(error: BaseException) -> list[str]:
    """``error`` as a traceback for the log: like Python's, with the causes first, but
    with ``code_path`` paths and a scrubbed message."""
    chain = []
    current: BaseException | None = error
    while current is not None and current not in chain:
        chain.append(current)
        current = current.__cause__ or (
            None if current.__suppress_context__ else current.__context__
        )
    lines = []
    for index, link in enumerate(reversed(chain)):
        if index:
            lines.append("Which led to:")
        lines.append("Traceback (most recent call last):")
        for frame in frames(link):
            lines.append(f"  {frame.path}:{frame.line} in {frame.function}")
            if frame.code:
                lines.append(f"    {frame.code}")
        lines.append(describe(link))
    return lines


class LogFormatter(logging.Formatter):
    """One line per event, and tracebacks through ``error_lines``."""

    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)s %(name)s: %(message)s")

    def formatException(self, ei) -> str:  # noqa: N802 - logging's name
        return "\n".join(error_lines(ei[1]))


class RunLog:
    """The log files of one run of Nodus: opened by ``start`` and closed by ``stop``, so
    a test that starts one leaves the logging of the process as it found it."""

    def __init__(self, logs_dir: Path) -> None:
        self.logs_dir = logs_dir
        self._handler: logging.Handler | None = None
        self._crash_file: TextIO | None = None
        self._faulthandler_was_on = False

    @property
    def log_file(self) -> Path:
        return self.logs_dir / LOG_FILENAME

    def start(self) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            self.log_file, maxBytes=MAX_BYTES, backupCount=KEPT_FILES, encoding="utf-8"
        )
        handler.setFormatter(LogFormatter())
        logger = logging.getLogger(LOGGER_NAME)
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        self._handler = handler
        crash_log = self.logs_dir / CRASH_FILENAME
        # Its own file, since Windows cannot rotate a file another handle keeps open.
        too_big = crash_log.exists() and crash_log.stat().st_size > MAX_BYTES
        self._crash_file = crash_log.open("w" if too_big else "a", encoding="utf-8")
        self._faulthandler_was_on = faulthandler.is_enabled()
        faulthandler.enable(self._crash_file)

    def stop(self) -> None:
        if self._handler is not None:
            logging.getLogger(LOGGER_NAME).removeHandler(self._handler)
            self._handler.close()
            self._handler = None
        if self._crash_file is not None:
            faulthandler.disable()
            self._crash_file.close()
            self._crash_file = None
            if self._faulthandler_was_on:
                _restore_faulthandler()


def _restore_faulthandler() -> None:
    """Back to the console, as before ``start``, where there is a real one to write to."""
    with contextlib.suppress(AttributeError, ValueError, OSError):  # no console, or no file
        faulthandler.enable(sys.__stderr__)
