"""Base class for the main sections."""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from nodus.ui.theme.design import Space
from nodus.ui.widgets.segmented import TabBar
from nodus.ui.widgets.style import set_style_property


class Page(QWidget):
    """A main section: a title and a content area that subclasses fill.

    ``refresh`` runs every time the page is shown, so it always reflects current data.
    """

    HEADER_HEIGHT = 44

    def __init__(self, title: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Space.XXXL, Space.XXL, Space.XXXL, Space.XXL)
        layout.setSpacing(Space.L)
        header = QWidget()
        # As tall as the selection bar, which takes the header's place, so nothing below
        # moves when rows are chosen.
        header.setFixedHeight(self.HEADER_HEIGHT)
        self._header = QHBoxLayout(header)
        self._header.setContentsMargins(0, 0, 0, 0)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("PageTitle")
        self._header.addWidget(self.title_label)
        self._header.addStretch()
        self._header_widgets: list[QWidget] = []
        self._selection_bar: QWidget | None = None
        layout.addWidget(header)
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(Space.L)
        layout.addLayout(self.content_layout, stretch=1)

    def add_header_button(self, text: str, primary: bool = False) -> QPushButton:
        """Adds a button to the right of the title, for the page's main actions."""
        button = QPushButton(text)
        button.setObjectName("PrimaryButton" if primary else "SecondaryButton")
        self.add_header_widget(button)
        return button

    def add_header_widget(self, widget: QWidget) -> None:
        """Adds a control to the right of the title, e.g. a month selector."""
        self._header.addWidget(widget)
        self._header_widgets.append(widget)

    def set_tabs(self, labels: list[str], descriptions: list[str]) -> TabBar:
        """Puts tabs for the page's views under the title, each with a line that says
        what its view shows. The header stays for what affects the whole page."""
        tabs = TabBar(labels)
        description = QLabel(descriptions[0])
        description.setObjectName("TabDescription")
        set_style_property(description, "muted", True)
        tabs.changed.connect(lambda index: description.setText(descriptions[index]))
        self.tab_description = description
        block = QVBoxLayout()
        block.setSpacing(Space.M)
        row = QHBoxLayout()
        row.addWidget(tabs)
        row.addStretch()
        block.addLayout(row)
        block.addWidget(description)
        self.content_layout.insertLayout(0, block)
        return tabs

    def set_selection_bar(self, bar: QWidget) -> None:
        """Puts ``bar`` in the header, hidden, to take the place of the header's controls
        while several rows are chosen (see ``show_selection_bar``)."""
        self._selection_bar = bar
        self._header.addWidget(bar, stretch=1)
        bar.hide()

    def show_selection_bar(self, shown: bool) -> None:
        """Swaps the header's controls for the selection bar, or back."""
        if self._selection_bar is None or self._selection_bar.isVisibleTo(self) == shown:
            return
        self._selection_bar.setVisible(shown)
        for widget in self._header_widgets:
            widget.setVisible(not shown)

    def refresh(self) -> None:
        """Reloads the page's data. Pages that show stored data override it."""
