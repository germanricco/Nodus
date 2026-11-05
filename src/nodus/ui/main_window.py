"""Main application window."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from nodus.services.container import Services
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import PageId
from nodus.ui.pages.page import Page, PlaceholderPage
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.sidebar import Sidebar
from nodus.ui.widgets.top_bar import TopBar


class MainWindow(QMainWindow):
    """Sidebar on the left; top bar and the current page on the right."""

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__()
        self.setWindowTitle("Nodus")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)

        self.sidebar = Sidebar(services, event_bus, theme_manager)
        self.top_bar = TopBar(theme_manager)
        self._stack = QStackedWidget()
        self._stack.setObjectName("PageStack")
        self._pages: dict[PageId, Page] = {
            page_id: PlaceholderPage(page_id.label) for page_id in PageId
        }
        for page in self._pages.values():
            self._stack.addWidget(page)

        content = QWidget()
        content.setObjectName("ContentArea")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self.top_bar)
        content_layout.addWidget(self._stack, stretch=1)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(content, stretch=1)
        self.setCentralWidget(central)

        self.sidebar.page_requested.connect(self.show_page)
        self.show_page(PageId.DASHBOARD)

    @property
    def current_page(self) -> Page:
        return self._stack.currentWidget()

    def page(self, page_id: PageId) -> Page:
        return self._pages[page_id]

    def show_page(self, page_id: PageId) -> None:
        page = self._pages[page_id]
        page.refresh()
        self._stack.setCurrentWidget(page)
        self.sidebar.select(page_id)
