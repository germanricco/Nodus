"""Ayuda opens from F1, the «?» and Ajustes; it lists every topic and every shortcut."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from nodus.ui import main_window
from nodus.ui.dialogs.help_dialog import HelpDialog
from nodus.ui.help_texts import HELP_TOPICS
from nodus.ui.navigation import PageId
from nodus.ui.shortcuts import SHORTCUTS


@pytest.fixture
def opened(monkeypatch) -> list[HelpDialog]:
    dialogs = []
    monkeypatch.setattr(main_window.HelpDialog, "exec", lambda self: dialogs.append(self))
    return dialogs


def test_f1_opens_it(qtbot, window, opened):
    window.activateWindow()
    qtbot.keyClick(window, Qt.Key.Key_F1)

    assert len(opened) == 1


def test_the_question_mark_and_settings_open_it(window, opened):
    window.top_bar.help_button.click()
    window.page(PageId.SETTINGS).help_requested.emit()

    assert len(opened) == 2
    assert window.top_bar.help_button.toolTip() == "Ayuda (F1)"


@pytest.mark.parametrize("topic", HELP_TOPICS, ids=lambda topic: topic.title)
def test_every_topic_is_written_in_full_sentences(topic):
    assert topic.title and topic.paragraphs
    assert all(paragraph.endswith(".") for paragraph in topic.paragraphs)


def test_choosing_a_topic_shows_its_text(qtbot):
    dialog = HelpDialog(guide_hidden=False)
    qtbot.addWidget(dialog)

    dialog.topic_list.setCurrentRow(2)

    assert HELP_TOPICS[2].title in dialog.topic_text.toPlainText()
    assert HELP_TOPICS[2].paragraphs[0][:40] in dialog.topic_text.toPlainText()


def test_the_shortcuts_tab_lists_the_whole_table(qtbot):
    dialog = HelpDialog(guide_hidden=False)
    qtbot.addWidget(dialog)
    dialog.tabs.set_index(1)

    keys = [label.text() for label in dialog.findChildren(QLabel, "ShortcutKeys")]

    assert dialog.pages.currentIndex() == 1
    assert keys == [shortcut.keys for shortcut in SHORTCUTS]


def test_primeros_pasos_comes_back_from_help(qtbot, window, services, pesos, monkeypatch):
    services.guide.dismiss()
    dialog = HelpDialog(guide_hidden=True)
    qtbot.addWidget(dialog)
    dialog.guide_requested.connect(window.show_guide)

    dialog.guide_button.click()

    assert not services.settings.guide_dismissed()
    assert window.page(PageId.DASHBOARD).guide_card.isVisible()


def test_primeros_pasos_is_offered_only_when_put_away(qtbot):
    dialog = HelpDialog(guide_hidden=False)
    qtbot.addWidget(dialog)

    assert dialog.guide_button.isHidden()


def test_the_tour_starts_from_help(qtbot, window, pesos):
    dialog = HelpDialog(guide_hidden=False)
    qtbot.addWidget(dialog)
    dialog.tour_requested.connect(window.start_tour)

    dialog.tour_button.click()

    assert window.tour.isVisible()
    assert window.tour.steps[-1].target == "help"
