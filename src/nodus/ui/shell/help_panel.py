"""Ayuda, as a panel at the right of the window: the topics, one topic, the shortcuts.

A panel and not a dialog, so the window stays in sight while reading: the pages a topic
talks about light up in the sidebar, and «Ir a…» opens them without closing the help.
"""

from __future__ import annotations

import re
from html import escape

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from nodus.i18n import N_, _
from nodus.ui.shortcuts import CLOSE_HELP, SHORTCUT_GROUPS, SHORTCUTS, Shortcut
from nodus.ui.text.help_texts import HELP_SECTIONS, HELP_TOPICS, TOPICS_BY_KEY, HelpTopic
from nodus.ui.text.labels import TOUR_LABEL
from nodus.ui.theme.design import IconSize, Layout, Space
from nodus.ui.theme.icons import icon
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.empty_state import EmptyState
from nodus.ui.widgets.style import muted_label, scrolling, secondary_button, separator

INDEX, TOPIC, SHORTCUTS_VIEW = range(3)
SHORTCUTS_TITLE = N_("Atajos de teclado")
TOPIC_ICON = "info"  # a topic about no page in particular


def topic_html(topic: HelpTopic) -> str:
    """The intro, then each paragraph; the screen's names, between «» (“” in English),
    in bold."""

    def paragraph(text: str) -> str:
        html = re.sub(r"([«“])([^»”]+)([»”])", r"\1<b>\2</b>\3", escape(_(text)))
        return "<p>" + html + "</p>"

    return "".join(paragraph(text) for text in (topic.intro, *topic.paragraphs))


def matches(topic: HelpTopic, words: str) -> bool:
    """Whether every word typed is in the topic's title or text, as shown, ignoring case."""
    text = " ".join(_(text) for text in (topic.title, topic.intro, *topic.paragraphs)).casefold()
    return all(word in text for word in words.casefold().split())


class HelpPanel(QFrame):
    """Three views: the topics by section, with a search and the shortcuts at the end;
    one topic, with «Ir a…» and its related topics; and the shortcuts by where they
    work. ``spotlight_changed`` gives the pages to light up in the sidebar (none outside
    a topic); ``page_requested`` asks for one. At the foot of the topics, the guided
    tour.
    """

    closed = Signal()
    page_requested = Signal(object)  # PageId
    spotlight_changed = Signal(object)  # tuple[PageId, ...]
    tour_requested = Signal()

    def __init__(self, theme_manager: ThemeManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HelpPanel")
        self.setFixedWidth(Layout.HELP_PANEL_WIDTH)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Esc closes it
        self.topic: HelpTopic | None = None
        self._topic_buttons: dict[str, QPushButton] = {}
        self._icon_buttons: list[tuple[QPushButton, str]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Space.XL, Space.L, Space.L, Space.L)
        layout.setSpacing(Space.M)
        header = QHBoxLayout()
        title = QLabel(_("Ayuda"))
        title.setObjectName("DialogTitle")
        header.addWidget(title)
        header.addStretch()
        self.close_button = QPushButton()
        self.close_button.setObjectName("PanelClose")
        self.close_button.setToolTip(_("Cerrar la ayuda (Esc)"))
        self.close_button.setAccessibleName(_("Cerrar la ayuda"))
        self.close_button.setIconSize(QSize(IconSize.L, IconSize.L))
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.clicked.connect(self.close_panel)
        self._icon_buttons.append((self.close_button, "close"))
        header.addWidget(self.close_button)
        layout.addLayout(header)

        self.views = QStackedWidget()
        self.views.addWidget(self._index_view())
        self.views.addWidget(self._topic_view())
        self.views.addWidget(self._shortcuts_view())
        layout.addWidget(self.views, stretch=1)

        self._apply_theme(theme_manager.theme)
        theme_manager.theme_changed.connect(self._apply_theme)

    # Showing

    def show_index(self) -> None:
        self.topic = None
        self.views.setCurrentIndex(INDEX)
        self.spotlight_changed.emit(())

    def show_topic(self, topic: HelpTopic) -> None:
        self.topic = topic
        self.topic_title.setText(_(topic.title))
        self.topic_text.setText(topic_html(topic))
        self.go_button.setVisible(bool(topic.pages))
        if topic.pages:
            self.go_button.setText(_("Ir a {page}").format(page=topic.pages[0].label))
        for button in self._related_buttons:
            button.setParent(None)  # gone now, not when the event loop deletes it
            button.deleteLater()
        self._related_buttons = []
        for key in topic.related:
            button = self._link(_(TOPICS_BY_KEY[key].title))
            button.clicked.connect(lambda _c=False, k=key: self.show_topic(TOPICS_BY_KEY[k]))
            self._related_layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)
            self._related_buttons.append(button)
        self.related_label.setVisible(bool(topic.related))
        self.views.setCurrentIndex(TOPIC)
        self.spotlight_changed.emit(topic.pages)

    def show_shortcuts(self) -> None:
        self.topic = None
        self.views.setCurrentIndex(SHORTCUTS_VIEW)
        self.spotlight_changed.emit(())

    def close_panel(self) -> None:
        self.hide()
        self.spotlight_changed.emit(())
        self.closed.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if CLOSE_HELP.matches(event):
            self.close_panel()
            return
        super().keyPressEvent(event)

    # The topics

    def _index_view(self) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.M)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(_("Buscar en la ayuda…"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.filter)
        layout.addWidget(self.search_input)

        topics = QWidget()
        topics.setObjectName("HelpBody")
        self._topics_layout = QVBoxLayout(topics)
        self._topics_layout.setContentsMargins(0, 0, Space.S, 0)
        self._topics_layout.setSpacing(Space.XXS)
        self._section_labels: dict[str, QLabel] = {}
        for section in HELP_SECTIONS:
            label = QLabel(_(section).upper())
            label.setObjectName("SectionLabel")
            self._topics_layout.addWidget(label)
            self._section_labels[section] = label
            for topic in HELP_TOPICS:
                if topic.section == section:
                    button = self._topic_button(
                        _(topic.title), topic.pages[0].icon_name if topic.pages else TOPIC_ICON
                    )
                    button.clicked.connect(lambda _c=False, t=topic: self.show_topic(t))
                    self._topics_layout.addWidget(button)
                    self._topic_buttons[topic.key] = button
        self.shortcuts_label = QLabel(_("TECLADO Y MOUSE"))
        self.shortcuts_label.setObjectName("SectionLabel")
        self._topics_layout.addWidget(self.shortcuts_label)
        self.shortcuts_button = self._topic_button(_(SHORTCUTS_TITLE), "keyboard")
        self.shortcuts_button.clicked.connect(self.show_shortcuts)
        self._topics_layout.addWidget(self.shortcuts_button)
        self.no_results = EmptyState(_("Ningún tema habla de eso."), compact=True)
        self.no_results.hide()
        self._topics_layout.addWidget(self.no_results)
        self._topics_layout.addStretch()
        layout.addWidget(scrolling(topics, horizontal=False), stretch=1)

        foot = QHBoxLayout()
        foot.setSpacing(Space.S)
        self.tour_button = self._foot_button(_(TOUR_LABEL), self.tour_requested)
        foot.addWidget(self.tour_button)
        foot.addStretch()
        layout.addLayout(foot)
        return view

    def filter(self, words: str) -> None:
        """Leaves only the topics with every word typed, and the sections that keep one."""
        shown = 0
        for section in HELP_SECTIONS:
            keep = [t for t in HELP_TOPICS if t.section == section and matches(t, words)]
            for topic in HELP_TOPICS:
                if topic.section == section:
                    self._topic_buttons[topic.key].setVisible(topic in keep)
            self._section_labels[section].setVisible(bool(keep))
            shown += len(keep)
        searching = bool(words.strip())
        self.shortcuts_label.setVisible(not searching)
        self.shortcuts_button.setVisible(not searching)
        self.no_results.setVisible(searching and shown == 0)

    def visible_topics(self) -> list[str]:
        return [key for key, button in self._topic_buttons.items() if not button.isHidden()]

    def _topic_button(self, text: str, icon_name: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("HelpTopic")
        button.setIconSize(QSize(IconSize.L, IconSize.L))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._icon_buttons.append((button, icon_name))
        return button

    def _foot_button(self, text: str, signal: Signal) -> QPushButton:
        button = secondary_button(text, signal)
        return button

    # One topic

    def _back_button(self) -> QPushButton:
        button = self._link(_("‹ Temas"))
        button.clicked.connect(self.show_index)
        return button

    @staticmethod
    def _link(text: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("LinkButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def _topic_view(self) -> QWidget:
        """The text flows into «Ir a…» and the related topics, all scrolling together."""
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.S)
        layout.addWidget(self._back_button(), alignment=Qt.AlignmentFlag.AlignLeft)
        body = QWidget()
        body.setObjectName("HelpBody")
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 0, Space.S, 0)
        column.setSpacing(Space.M)
        self.topic_title = QLabel()
        self.topic_title.setObjectName("HelpTitle")
        self.topic_title.setWordWrap(True)
        column.addWidget(self.topic_title)
        self.topic_text = QLabel()
        self.topic_text.setTextFormat(Qt.TextFormat.RichText)
        self.topic_text.setWordWrap(True)
        self.topic_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        column.addWidget(self.topic_text)
        self.go_button = QPushButton()
        self.go_button.setObjectName("PrimaryButton")
        self.go_button.clicked.connect(self._go)
        column.addWidget(self.go_button, alignment=Qt.AlignmentFlag.AlignLeft)
        column.addSpacing(Space.S)
        self.related_label = QLabel(_("RELACIONADOS"))
        self.related_label.setObjectName("HelpRelated")
        column.addWidget(self.related_label)
        self._related_layout = QVBoxLayout()
        self._related_layout.setSpacing(Space.XS)
        self._related_buttons: list[QPushButton] = []
        column.addLayout(self._related_layout)
        column.addStretch()
        layout.addWidget(scrolling(body, horizontal=False), stretch=1)
        return view

    def _go(self) -> None:
        if self.topic is not None and self.topic.pages:
            self.page_requested.emit(self.topic.pages[0])

    # The shortcuts

    def _shortcuts_view(self) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.S)
        layout.addWidget(self._back_button(), alignment=Qt.AlignmentFlag.AlignLeft)
        title = QLabel(_(SHORTCUTS_TITLE))
        title.setObjectName("HelpTitle")
        layout.addWidget(title)

        table = QWidget()
        table.setObjectName("HelpBody")
        groups = QVBoxLayout(table)
        groups.setContentsMargins(0, 0, Space.S, 0)
        groups.setSpacing(Space.XS)
        for group in SHORTCUT_GROUPS:
            label = QLabel(_(group).upper())
            label.setObjectName("SectionLabel")
            label.setWordWrap(True)
            groups.addWidget(label)
            groups.addWidget(self._shortcut_group([s for s in SHORTCUTS if s.group == group]))
        groups.addStretch()
        layout.addWidget(scrolling(table, horizontal=False), stretch=1)
        return view

    @classmethod
    def _shortcut_group(cls, shortcuts: list[Shortcut]) -> QFrame:
        """The shortcuts of one group in a box, as a menu reads: what each does on the
        left, its keys on the right, a thin line between them."""
        box = QFrame()
        box.setObjectName("ShortcutGroup")
        rows = QVBoxLayout(box)
        rows.setContentsMargins(Space.M, Space.XS, Space.M, Space.XS)
        rows.setSpacing(Space.XS)
        for index, shortcut in enumerate(shortcuts):
            if index:
                rows.addWidget(separator())
            row = QHBoxLayout()
            row.setSpacing(Space.M)
            text = QLabel(_(shortcut.text))
            text.setWordWrap(True)
            row.addWidget(text, stretch=1)
            row.addLayout(cls._keys(shortcut.keys))
            rows.addLayout(row)
        return box

    @staticmethod
    def _keys(keys: tuple[str, ...]) -> QHBoxLayout:
        """Each key drawn as a key, with «+» between those pressed together."""
        row = QHBoxLayout()
        row.setSpacing(Space.XS)
        for index, key in enumerate(keys):
            if index:
                plus = muted_label("+")
                row.addWidget(plus)
            cap = QLabel(_(key))
            cap.setObjectName("KeyCap")
            # Its own height, centered on its row, however many lines the text beside has.
            cap.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            row.addWidget(cap)
        return row

    def _apply_theme(self, theme: Theme) -> None:
        for button, name in self._icon_buttons:
            button.setIcon(icon(name, theme.text_muted))
