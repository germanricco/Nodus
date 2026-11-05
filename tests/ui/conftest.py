"""Fixtures for interface tests."""

import pytest
from PySide6.QtWidgets import QApplication

from nodus.ui.event_bus import EventBus
from nodus.ui.main_window import MainWindow
from nodus.ui.theme.theme import ThemeMode
from nodus.ui.theme.theme_manager import ThemeManager


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def theme_manager(qapp: QApplication) -> ThemeManager:
    return ThemeManager(qapp, ThemeMode.LIGHT)


@pytest.fixture
def window(qtbot, services, event_bus, theme_manager) -> MainWindow:
    main_window = MainWindow(services, event_bus, theme_manager)
    qtbot.addWidget(main_window)
    main_window.show()
    return main_window
