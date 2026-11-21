"""``--smoke-test`` passes on a whole program and names what a built one lacks."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from factories import light_theme

from nodus import smoke_test
from nodus.config.paths import AppPaths
from nodus.services.app.changelog import changelog_files
from nodus.smoke_test import SmokeTest, stylesheet_problems, window_problems
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
    monkeypatch.setattr(smoke_test, "load_changelog", lambda language: [])
    english_missing = {"en": [Path("nowhere/CHANGELOG.en.md")]}
    monkeypatch.setattr(
        smoke_test,
        "changelog_files",
        lambda: {
            language: english_missing.get(language.value, files)
            for language, files in changelog_files().items()
        },
    )
    monkeypatch.setattr(smoke_test, "has_catalog", lambda language: language.value == "es")
    monkeypatch.setattr(smoke_test, "has_qt_texts", lambda language: language.value == "en")

    problems = window_problems(window)

    assert problems == [
        "Qt's es texts are missing",
        "the en catalog of Nodus's texts is missing",
        f"the changelog has no section for {smoke_test.__version__}",
        "the en changelog is missing",
    ]


def test_a_font_left_out_of_the_build_is_named(window, monkeypatch):
    """Without its font Nodus still opens, in a system font that takes other room."""
    monkeypatch.setattr(smoke_test, "FONT_FAMILY", "A Font Nodus Lacks")

    assert window_problems(window) == [
        "the A Font Nodus Lacks font is missing: text takes another font's room"
    ]


def test_a_stylesheet_image_that_is_not_there_is_named_once(tmp_path):
    """As in a build where the icons folder came out as «MultiplexedPath('…')»."""
    arrow = tmp_path / "chevron-down.svg"
    arrow.write_text("<svg/>", encoding="utf-8")
    broken = "MultiplexedPath('/opt/nodus/icons')/chevron-left.svg"
    stylesheet = f"a {{ image: url({arrow.as_posix()}); }} b {{ image: url({broken}); }}" * 2

    assert stylesheet_problems(stylesheet) == [f"the stylesheet image {broken} is missing"]


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
