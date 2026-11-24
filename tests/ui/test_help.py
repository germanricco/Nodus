"""Ayuda opens at the side from F1, the «?» and Ajustes, on the topic of the page shown,
and lights up in the sidebar the pages a topic talks about."""

from importlib import resources

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QFrame, QLabel

from nodus.ui.navigation import DetailId, PageId
from nodus.ui.shell.help_panel import INDEX, SHORTCUTS_VIEW, topic_html
from nodus.ui.shortcuts import SHORTCUT_GROUPS, SHORTCUTS
from nodus.ui.text.help_texts import HELP_SECTIONS, HELP_TOPICS, TOPICS_BY_KEY


def lit(window) -> set[PageId]:
    return {
        page_id
        for page_id in PageId
        if window.sidebar.nav_button(page_id).property("spotlight") is True
    }


def test_f1_opens_and_closes_it(qtbot, window):
    window.activateWindow()

    qtbot.keyClick(window, Qt.Key.Key_F1)
    assert window.help_panel.isVisible()

    qtbot.keyClick(window, Qt.Key.Key_F1)
    assert not window.help_panel.isVisible()


def test_the_question_mark_and_settings_open_it(window):
    window.top_bar.help_button.click()
    assert window.help_panel.isVisible()
    window.top_bar.help_button.click()

    window.page(PageId.SETTINGS).help_requested.emit()

    assert window.help_panel.isVisible()
    assert window.top_bar.help_button.toolTip() == "Ayuda (F1)"


def test_it_opens_on_the_topic_of_the_page_shown(window, pesos):
    window.show_page(PageId.GOALS)
    window.show_help()
    assert window.help_panel.topic is TOPICS_BY_KEY["goals"]

    window.show_detail(DetailId.ACCOUNT, pesos.id)
    window.toggle_help()
    window.toggle_help()
    assert window.help_panel.topic is TOPICS_BY_KEY["accounts"]


def test_on_inicio_it_opens_on_the_list_of_topics(window):
    window.show_page(PageId.DASHBOARD)
    window.show_help()

    assert window.help_panel.views.currentIndex() == INDEX
    assert lit(window) == set()
    assert len(window.help_panel.visible_topics()) == len(HELP_TOPICS)


def test_a_topic_lights_up_its_pages_until_left(window):
    panel = window.help_panel
    window.show_help(TOPICS_BY_KEY["categories"])
    assert lit(window) == {PageId.CATEGORIES, PageId.PAYEES, PageId.TAGS}

    panel.show_index()
    assert lit(window) == set()

    window.show_help(TOPICS_BY_KEY["budgets"])
    panel.close_button.click()
    assert lit(window) == set()
    assert not panel.isVisible()


def test_esc_closes_it(qtbot, window):
    window.show_help()

    qtbot.keyClick(window.help_panel, Qt.Key.Key_Escape)

    assert not window.help_panel.isVisible()


def test_go_to_opens_the_page_and_keeps_the_help(window):
    window.show_help(TOPICS_BY_KEY["budgets"])
    assert window.help_panel.go_button.text() == "Ir a Presupuestos"

    window.help_panel.go_button.click()

    assert window.current_page is window.page(PageId.BUDGETS)
    assert window.help_panel.isVisible()


def test_related_topics_open_from_a_topic(window):
    window.show_help(TOPICS_BY_KEY["goals"])

    window.help_panel._related_buttons[0].click()

    assert window.help_panel.topic is TOPICS_BY_KEY[TOPICS_BY_KEY["goals"].related[0]]


def test_the_search_keeps_only_matching_topics(window):
    panel = window.help_panel
    window.show_help()
    panel.show_index()

    panel.search_input.setText("cuotas adelantar")
    assert panel.visible_topics() == ["installments"]

    panel.search_input.setText("xyzzy")
    assert panel.visible_topics() == []
    assert not panel.no_results.isHidden()

    panel.search_input.clear()
    assert len(panel.visible_topics()) == len(HELP_TOPICS)


@pytest.mark.parametrize("topic", HELP_TOPICS, ids=lambda topic: topic.key)
def test_every_topic_is_complete(topic):
    assert topic.section in HELP_SECTIONS
    assert topic.intro.endswith(".")
    assert topic.paragraphs
    assert all(paragraph.endswith(".") for paragraph in topic.paragraphs)
    assert all(key in TOPICS_BY_KEY and key != topic.key for key in topic.related)


def test_screen_names_are_bold():
    html = topic_html(TOPICS_BY_KEY["goals"])

    assert "«<b>Agregar meta</b>»" in html


def test_the_shortcuts_are_listed_by_group(window):
    panel = window.help_panel
    window.show_help()

    panel.shortcuts_button.click()

    assert panel.views.currentIndex() == SHORTCUTS_VIEW
    caps = [label.text() for label in panel.findChildren(QLabel, "KeyCap")]
    assert caps == [
        key for group in SHORTCUT_GROUPS for s in SHORTCUTS if s.group == group for key in s.keys
    ]
    assert {shortcut.group for shortcut in SHORTCUTS} == set(SHORTCUT_GROUPS)
    assert len({(s.keys, s.group) for s in SHORTCUTS}) == len(SHORTCUTS)


def test_the_tour_starts_from_help_and_the_help_makes_way(window, pesos):
    window.show_help()

    window.help_panel.tour_button.click()

    assert not window.help_panel.isVisible()
    assert window.tour.isVisible()


@pytest.mark.parametrize("shortcut", [s for s in SHORTCUTS if s.qt_keys], ids=lambda s: s.text)
def test_a_shortcut_answers_its_keys_and_no_others(shortcut):
    def press(key, modifiers=Qt.KeyboardModifier.NoModifier):
        return QKeyEvent(QEvent.Type.KeyPress, key, modifiers)

    own = shortcut.modifier
    for key in shortcut.qt_keys:
        assert shortcut.matches(press(key, own))
        assert shortcut.matches(press(key, own | Qt.KeyboardModifier.KeypadModifier))
        assert not shortcut.matches(press(key, own | Qt.KeyboardModifier.ControlModifier))
    assert not shortcut.matches(press(Qt.Key.Key_A))


def test_in_english_screen_names_are_bold_between_english_quotes(english):
    html = topic_html(TOPICS_BY_KEY["goals"])

    assert "“<b>Add goal</b>”" in html


def test_in_english_the_window_and_its_help_speak_english(english, window):
    """The sidebar names its pages in English and the help searches the English text."""
    panel = window.help_panel
    window.show_help()
    panel.show_index()

    panel.search_input.setText("installments ahead")

    assert panel.visible_topics() == ["installments"]
    assert PageId.BUDGETS.label == "Budgets"


def shortcut_rows(window) -> tuple[list[QLabel], list[QLabel]]:
    """What each shortcut does and its keys, as the help draws them."""
    window.show()
    window.show_help()
    window.help_panel.shortcuts_button.click()
    QApplication.processEvents()
    box = window.help_panel.views.currentWidget()
    texts = [
        label
        for group in box.findChildren(QFrame, "ShortcutGroup")
        for label in group.findChildren(QLabel)
        if label.wordWrap()
    ]
    return texts, box.findChildren(QLabel, "KeyCap")


def one_line_each_and_keys_alike(window) -> None:
    texts, caps = shortcut_rows(window)
    line = texts[0].fontMetrics().lineSpacing()
    assert [t.text() for t in texts if t.height() >= 2 * line] == []
    assert len({cap.height() for cap in caps}) == 1


def test_each_shortcut_says_it_in_one_line_with_keys_all_alike(window):
    one_line_each_and_keys_alike(window)


def test_in_english_too(english, window):
    one_line_each_and_keys_alike(window)


def test_each_topic_has_an_icon_of_its_own():
    icons = [topic.icon_name for topic in HELP_TOPICS]

    assert len(set(icons)) == len(icons)
    assert all(resources.files("nodus.ui.icons").joinpath(f"{n}.svg").is_file() for n in icons)
