"""Base class for the main sections."""

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from nodus.ui.theme.design import Layout, Space
from nodus.ui.widgets.elided_label import ElidedLabel
from nodus.ui.widgets.inputs.segmented import TabBar
from nodus.ui.widgets.style import muted_label, scrolling


class PageHeader(QWidget):
    """A page's title with its buttons («Agregar…», «Editar», «⋯») on one row, and its
    filters (the period, the search) beside them while everything fits. When it does not,
    the filters go to a second row under the title instead of squeezing the row, and a
    title too long for what is left ends in «…».

    The rows keep their height while several rows are chosen, as the selection bar takes
    the place of the buttons and filters, so nothing below moves.
    """

    def __init__(self, title: str) -> None:
        super().__init__()
        rows = QVBoxLayout(self)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(Space.S)
        self.top = QHBoxLayout()
        self.top.setContentsMargins(0, 0, 0, 0)
        self.title_label = ElidedLabel(title)
        self.title_label.setObjectName("PageTitle")
        # Its whole width while there is room; less, ending in «…», when there is not.
        self.title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.top.addWidget(self.title_label)
        self.top.addStretch()
        self.filters = QWidget()
        filters = QHBoxLayout(self.filters)
        filters.setContentsMargins(0, 0, 0, 0)
        self._filters_layout = filters
        self.filters.hide()  # until it holds something
        self.top.addWidget(self.filters)
        rows.addLayout(self.top)
        self._second = QHBoxLayout()
        self._second.setContentsMargins(0, 0, 0, 0)
        rows.addLayout(self._second)
        self._frozen = False
        self._set_two_rows(False)

    def add_filter(self, widget: QWidget) -> None:
        self._filters_layout.addWidget(widget)
        self.filters.show()

    def freeze(self, frozen: bool) -> None:
        """Keeps the rows as they are while the selection bar is up: without the
        buttons and filters, everything would fit in one row."""
        self._frozen = frozen
        if not frozen:
            self.arrange()

    def two_rows(self) -> bool:
        return self.filters.parentWidget() is self and self._second.indexOf(self.filters) >= 0

    def arrange(self) -> None:
        """One row if the title, buttons and filters fit side by side, else two."""
        if self._frozen:
            return
        # Without filters there is nothing to move down: the title gives way instead.
        crowded = not self.filters.isHidden() and self._one_row_width() > self.width()
        if crowded == self.two_rows():
            return
        if crowded:
            self.top.removeWidget(self.filters)
            self._second.addWidget(self.filters)
            self._second.addStretch()
        else:
            self._second.removeWidget(self.filters)
            while self._second.count():
                self._second.takeAt(0)
            # Back after the stretch, before the buttons, where it was.
            self.top.insertWidget(self.top.indexOf(self.title_label) + 2, self.filters)
        self._set_two_rows(crowded)

    def _one_row_width(self) -> int:
        """The width of everything shown, in one row, at its natural size."""
        widths = []
        for index in range(self.top.count()):
            item = self.top.itemAt(index)
            widget = item.widget()
            if widget is self.filters or (widget is not None and widget.isHidden()):
                continue
            widths.append(item.sizeHint().width())
        if not self.filters.isHidden():
            widths.append(self.filters.sizeHint().width())
        return sum(widths) + self.top.spacing() * (len(widths) - 1)

    def _set_two_rows(self, two: bool) -> None:
        height = Layout.HEADER_HEIGHT
        if two:
            height += Space.S + Layout.HEADER_HEIGHT
        self.setFixedHeight(height)

    def event(self, event: QEvent) -> bool:
        handled = super().event(event)
        # Something in it was shown, hidden or renamed, or it was resized.
        if event.type() in (QEvent.Type.LayoutRequest, QEvent.Type.Resize):
            self.arrange()
        return handled


class Page(QWidget):
    """A main section: a title and a content area that subclasses fill.

    ``refresh`` runs every time the page is shown, so it always reflects current data.
    Data changes call ``request_refresh``, which leaves a hidden page alone: refreshing
    every page opened before, on each change, made each save slower the more pages the
    user had visited.
    """

    HEADER_HEIGHT = Layout.HEADER_HEIGHT

    def __init__(self, title: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Space.XXXL, Space.XXL, Space.XXXL, Space.XXL)
        layout.setSpacing(Space.L)
        header = self.header = PageHeader(title)
        self._header = header.top
        self.title_label = header.title_label
        self._header_widgets: list[QWidget] = []
        self._selection_bar: QWidget | None = None
        layout.addWidget(header)
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(Space.L)
        layout.addLayout(self.content_layout, stretch=1)

    def scrolling_body(self) -> QVBoxLayout:
        """A column under the header that scrolls as a whole, for the page to fill."""
        container = QWidget()
        body = QVBoxLayout(container)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(Space.L)
        self.content_layout.addWidget(scrolling(container))
        return body

    def request_refresh(self, *_args: object) -> None:
        """Refreshes the page, unless the window put it aside: hidden in its stack, it
        is refreshed when shown again (``MainWindow.show_page``, or ``show_item`` for a
        detail page). Takes and ignores what the signal carries."""
        if self.parentWidget() is not None and self.isHidden():
            return
        self.refresh()

    def add_header_button(self, text: str, primary: bool = False) -> QPushButton:
        """Adds a button to the right of the title, for the page's main actions."""
        button = QPushButton(text)
        button.setObjectName("PrimaryButton" if primary else "SecondaryButton")
        self.add_header_widget(button)
        return button

    def add_header_widget(self, widget: QWidget) -> None:
        """Adds a control to the right of the title, beside the buttons (a «⋯»)."""
        self._header.addWidget(widget)
        self._header_widgets.append(widget)

    def add_header_filter(self, widget: QWidget) -> None:
        """Adds what narrows the page (the period, a search) to the right of the title,
        or under it when the header has no room (``PageHeader``)."""
        self.header.add_filter(widget)
        self._header_widgets.append(widget)

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)

    def set_tabs(self, labels: list[str], descriptions: list[str]) -> TabBar:
        """Puts tabs for the page's views under the title, each with a line that says
        what its view shows. The header stays for what affects the whole page."""
        tabs = TabBar(labels)
        description = muted_label(descriptions[0])
        description.setObjectName("TabDescription")
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
        if shown:
            self.header.freeze(True)
        self._selection_bar.setVisible(shown)
        for widget in self._header_widgets:
            widget.setVisible(not shown)
        if not shown:
            self.header.freeze(False)

    def refresh(self) -> None:
        """Reloads the page's data. Pages that show stored data override it."""
