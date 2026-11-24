"""What a screen reader and a hand need on every page: a name for every button that
shows only an icon, and targets of at least 24×24 px (WCAG 2.2, 2.5.8)."""

from datetime import date

import pytest
from demo_data import load_demo_data
from PySide6.QtWidgets import QAbstractButton, QApplication, QCheckBox, QWidget

from nodus.ui.navigation import DetailId, PageId
from nodus.ui.shell.main_window import MainWindow

TARGET = 24


def settle() -> None:
    for _ in range(5):
        QApplication.processEvents()


def describe(widget: QWidget) -> str:
    return f"{type(widget).__name__}#{widget.objectName()} {widget.toolTip()!r}"


def unnamed(root: QWidget) -> list[str]:
    return [
        describe(button)
        for button in root.findChildren(QAbstractButton)
        if button.isVisible() and not button.text() and not button.accessibleName()
    ]


def small(root: QWidget) -> list[str]:
    """Targets under 24 px; a check box counts its box with its text, all of it clicks."""
    found = []
    for widget in root.findChildren(QAbstractButton):
        if not widget.isVisible():
            continue
        size = widget.size()
        if size.width() < TARGET or size.height() < TARGET:
            found.append(f"{describe(widget)} {size.width()}×{size.height()}")
    return found


@pytest.fixture
def full(window: MainWindow, services) -> MainWindow:
    load_demo_data(services, date.today())
    window.resize(1280, 900)
    return window


def every_place(window: MainWindow):
    for page_id in PageId:
        window.show_page(page_id)
        settle()
        yield page_id.name, window
    for detail in DetailId:
        window.show_detail(detail, 1)
        settle()
        yield detail.name, window


def first_places(full: MainWindow, check) -> dict[str, str]:
    """Each problem once, with the first page it shows on."""
    found: dict[str, str] = {}
    for name, window in every_place(full):
        for problem in check(window):
            found.setdefault(problem, name)
    return found


def test_every_icon_button_has_a_name(full):
    assert first_places(full, unnamed) == {}


def test_every_target_is_at_least_24_px(full):
    assert first_places(full, small) == {}


def test_a_check_box_is_a_target_too():
    assert issubclass(QCheckBox, QAbstractButton)


def test_a_short_window_scrolls_the_help_instead_of_squeezing_its_topics(window):
    """A button's minimum target must not become the least it can be squeezed to."""
    window.resize(1000, 520)
    window.show_help()
    settle()

    squeezed = [
        button.text()
        for button in window.help_panel.findChildren(QAbstractButton)
        if button.isVisible() and button.height() < button.sizeHint().height()
    ]
    assert squeezed == []
