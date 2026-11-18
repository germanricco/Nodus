"""Starting Nodus's own processes: the installer of an update, or Nodus again."""

from __future__ import annotations

import subprocess
import sys

from nodus import is_installed


def launch_detached(command: list[str]) -> None:
    """Starts ``command`` as its own process, so it outlives Nodus closing."""
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(command, creationflags=flags, close_fds=True)


def restart_command(argv: list[str]) -> list[str]:
    """The command that opens this same Nodus again, with the same arguments: the
    program itself when installed, ``python -m nodus`` when run from the code."""
    if is_installed():
        return [sys.executable, *argv[1:]]
    return [sys.executable, "-m", "nodus", *argv[1:]]
