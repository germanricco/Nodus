"""Fixtures for interface tests."""

import pytest
from factories import light_theme
from PySide6.QtWidgets import QApplication

from nodus.ui.dialogs import form_dialog
from nodus.ui.event_bus import EventBus
from nodus.ui.shell.main_window import MainWindow
from nodus.ui.theme.theme import ThemeMode
from nodus.ui.theme.theme_manager import ThemeManager


@pytest.fixture(autouse=True)
def discard_questions(monkeypatch) -> list[str]:
    """Forms closed with changes discard them without the modal question, which would
    wait forever: tests close every shown dialog when they end. The list holds the
    questions asked, for the tests about it."""
    asked: list[str] = []

    def discard(_parent, title, *_args, **_kwargs) -> bool:
        asked.append(title)
        return True

    monkeypatch.setattr(form_dialog, "confirm", discard)
    return asked


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def theme_manager(qapp: QApplication) -> ThemeManager:
    return light_theme()


@pytest.fixture(params=[ThemeMode.LIGHT, ThemeMode.DARK], ids=["light", "dark"])
def theme(request, qapp: QApplication) -> ThemeManager:
    """Each theme in turn, for what has to look right in both."""
    return ThemeManager(qapp, request.param)


@pytest.fixture
def window(qtbot, services, event_bus, theme_manager) -> MainWindow:
    # The tour's offer is a modal question; tests/ui/test_tour.py asks for it.
    services.settings.set_tour_offered(True)
    main_window = MainWindow(services, event_bus, theme_manager)
    qtbot.addWidget(main_window)
    main_window.show()
    return main_window
