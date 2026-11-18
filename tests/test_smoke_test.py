"""``--smoke-test`` passes on a whole program and names what a built one lacks."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from factories import light_theme

from nodus import smoke_test
from nodus.config.paths import AppPaths
from nodus.smoke_test import SmokeTest, window_problems
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import PageId
from nodus.ui.shell.main_window import MainWindow


@pytest.fixture
def window(qtbot, services) -> MainWindow:
    services.settings.set_tour_offered(True)  # a modal question nobody would answer
    main_window = MainWindow(services, EventBus(), light_theme())
    qtbot.addWidget(main_window)
    main_window.show()
    return main_window


def test_a_whole_program_has_no_problems(window):
    assert window_problems(window) == []


def test_it_names_what_is_missing(window, monkeypatch):
    monkeypatch.setattr(smoke_test, "load_changelog", lambda: [])
    monkeypatch.setattr(smoke_test, "has_catalog", lambda language: language.value == "es")
    monkeypatch.setattr(smoke_test, "has_qt_texts", lambda language: language.value == "en")

    problems = window_problems(window)

    assert problems == [
        "Qt's es texts are missing",
        "the en catalog of Nodus's texts is missing",
        f"the changelog has no section for {smoke_test.__version__}",
    ]


def test_a_page_that_fails_is_named_and_the_rest_still_tried(window, monkeypatch):
    shown = []
    show_page = window.show_page

    def show(page_id):
        shown.append(page_id)
        if page_id is PageId.BUDGETS:
            raise ImportError("budgets_page")
        show_page(page_id)

    monkeypatch.setattr(window, "show_page", show)

    problems = window_problems(window)

    assert problems == ["page BUDGETS did not open: ImportError('budgets_page')"]
    assert shown == list(PageId)


def test_its_own_data_folder_is_removed_afterwards(monkeypatch):
    monkeypatch.delenv(AppPaths.DATA_DIR_ENV_VAR, raising=False)
    run = SmokeTest()
    folder = run.paths.data_dir
    assert folder.is_dir()

    run.close()

    assert not folder.exists()


def test_the_data_folder_set_by_the_workflow_is_kept(monkeypatch, tmp_path):
    monkeypatch.setenv(AppPaths.DATA_DIR_ENV_VAR, str(tmp_path))
    run = SmokeTest()

    run.close()

    assert run.paths.data_dir == tmp_path
    assert tmp_path.is_dir()


def test_nodus_opens_whole_and_exits_with_zero(tmp_path):
    """The run the release workflow makes on the built program, here from the source."""
    env = {**os.environ, AppPaths.DATA_DIR_ENV_VAR: str(tmp_path), "QT_QPA_PLATFORM": "offscreen"}

    result = subprocess.run(
        [sys.executable, "-m", "nodus", smoke_test.FLAG], env=env, timeout=60, check=False
    )

    log = (Path(tmp_path) / "logs" / "nodus.log").read_text(encoding="utf-8")
    assert result.returncode == 0, log
    assert "Smoke test passed" in log
