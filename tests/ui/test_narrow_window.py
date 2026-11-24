"""Every page fits the narrowest window with Ayuda open: nothing runs past the page or
hides behind a horizontal scroll bar. What has no room shortens, wraps or steps aside."""

from datetime import date

import pytest
from demo_data import load_demo_data
from PySide6.QtWidgets import QAbstractScrollArea, QApplication, QComboBox, QPushButton, QWidget

from nodus.ui.navigation import DetailId, PageId
from nodus.ui.shell.main_window import MainWindow


def settle() -> None:
    for _ in range(5):
        QApplication.processEvents()


def overflows(page: QWidget) -> list[str]:
    """What scrolls sideways, and the buttons and lists squeezed below their minimum."""
    found = []
    for widget in page.findChildren(QWidget):
        if not widget.isVisible():
            continue
        if isinstance(widget, QAbstractScrollArea) and widget.horizontalScrollBar().maximum():
            found.append(f"{type(widget).__name__} scrolls sideways")
        squeezed = widget.width() < widget.minimumSizeHint().width() - 1
        if isinstance(widget, (QComboBox, QPushButton)) and squeezed:
            found.append(f"{type(widget).__name__} {widget.accessibleName()} squeezed")
    return found


@pytest.fixture
def narrow(window: MainWindow, services) -> MainWindow:
    load_demo_data(services, date.today())
    window.resize(window.minimumWidth(), 900)
    return window


@pytest.mark.parametrize("page_id", list(PageId), ids=lambda p: p.name)
def test_every_page_fits(narrow, page_id):
    narrow.show_page(page_id)
    narrow.show_help()
    settle()

    assert overflows(narrow.page(page_id)) == []


@pytest.mark.parametrize("detail", list(DetailId), ids=lambda d: d.name)
def test_every_detail_page_fits(narrow, detail):
    narrow.show_detail(detail, 1)
    narrow.show_help()
    settle()

    assert overflows(narrow.detail(detail)) == []
