import sys
import time

from nodus.services.external.process import launch_detached


def test_a_detached_process_runs_on_its_own(tmp_path):
    """What restarts Nodus and starts the Windows installer, on either system."""
    done = tmp_path / "done.txt"

    # Written aside and renamed, so the file never shows up empty.
    aside = done.with_suffix(".tmp")
    script = (
        f"import os; open({str(aside)!r}, 'w').write('ok');"
        f" os.replace({str(aside)!r}, {str(done)!r})"
    )
    launch_detached([sys.executable, "-c", script])

    deadline = time.monotonic() + 20
    while not done.is_file() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert done.read_text() == "ok"
