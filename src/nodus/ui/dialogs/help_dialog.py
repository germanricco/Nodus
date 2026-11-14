"""Ayuda (F1): «Cómo se hace» for what is not obvious, and every shortcut."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from nodus.ui.help_texts import HELP_TOPICS, HelpTopic
from nodus.ui.shortcuts import SHORTCUTS
from nodus.ui.theme.design import Layout, Space
from nodus.ui.widgets.segmented import TabBar
from nodus.ui.widgets.style import set_style_property

HOW_TO, SHORTCUTS_TAB = range(2)


def topic_html(topic: HelpTopic) -> str:
    return "".join(f"<p>{escape(paragraph)}</p>" for paragraph in topic.paragraphs)


class HelpDialog(QDialog):
    """Two tabs: the topics in a list with the chosen one's text beside it, and the
    shortcuts table. At the foot, the guided tour and, when it was put away, Primeros
    pasos: choosing one closes the dialog and asks for it (``tour_requested``,
    ``guide_requested``).
    """

    tour_requested = Signal()
    guide_requested = Signal()

    def __init__(self, guide_hidden: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ayuda")
        self.resize(*Layout.HELP_SIZE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Space.XXL, Space.XL, Space.XXL, Space.XL)
        layout.setSpacing(Space.L)

        self.tabs = TabBar(["Cómo se hace", "Atajos"])
        layout.addWidget(self.tabs)
        self.pages = QStackedWidget()
        self.pages.addWidget(self._how_to_page())
        self.pages.addWidget(self._shortcuts_page())
        self.tabs.changed.connect(self.pages.setCurrentIndex)
        layout.addWidget(self.pages, stretch=1)

        buttons = QHBoxLayout()
        self.tour_button = self._button("Ver el recorrido", "SecondaryButton", self.tour_requested)
        buttons.addWidget(self.tour_button)
        self.guide_button = self._button(
            "Mostrar Primeros pasos", "SecondaryButton", self.guide_requested
        )
        self.guide_button.setVisible(guide_hidden)
        buttons.addWidget(self.guide_button)
        buttons.addStretch()
        close = QPushButton("Cerrar")
        close.setObjectName("PrimaryButton")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def _button(self, text: str, style: str, signal: Signal) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(style)
        button.clicked.connect(self.accept)
        button.clicked.connect(signal)
        return button

    def show_topic(self, row: int) -> None:
        topic = HELP_TOPICS[row]
        self.topic_text.setHtml(f"<h3>{escape(topic.title)}</h3>{topic_html(topic)}")

    def _how_to_page(self) -> QWidget:
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(Space.L)
        self.topic_list = QListWidget()
        self.topic_list.setObjectName("HelpTopics")
        self.topic_list.setFixedWidth(Layout.HELP_TOPICS_WIDTH)
        self.topic_list.addItems([topic.title for topic in HELP_TOPICS])
        self.topic_list.currentRowChanged.connect(self.show_topic)
        row.addWidget(self.topic_list)
        self.topic_text = QTextBrowser()
        self.topic_text.setObjectName("NewsText")
        row.addWidget(self.topic_text, stretch=1)
        self.topic_list.setCurrentRow(0)
        return page

    def _shortcuts_page(self) -> QWidget:
        table = QWidget()
        grid = QGridLayout(table)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(Space.XL)
        grid.setVerticalSpacing(Space.M)
        for row, shortcut in enumerate(SHORTCUTS):
            keys = QLabel(shortcut.keys)
            keys.setObjectName("ShortcutKeys")
            grid.addWidget(keys, row, 0)
            grid.addWidget(QLabel(shortcut.text), row, 1)
            where = QLabel(shortcut.where)
            set_style_property(where, "muted", True)
            where.setWordWrap(True)
            grid.addWidget(where, row, 2)
        grid.setColumnStretch(2, 1)
        grid.setRowStretch(len(SHORTCUTS), 1)
        return table
