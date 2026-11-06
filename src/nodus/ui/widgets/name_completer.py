"""Suggestions of existing names under a text field, as payees and tags use them."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QStringListModel, Qt
from PySide6.QtWidgets import QCompleter, QLineEdit


class NameCompleter(QObject):
    """Shows under ``line_edit`` the names ``matches`` returns for what is typed.

    The matching ignores case and accents and also finds names by their middle, which
    QCompleter's own filter cannot do, so the list is rebuilt on every keystroke and shown
    unfiltered. ``activated`` is the completer's: it carries the chosen name.
    """

    def __init__(self, line_edit: QLineEdit, matches: Callable[[str], list[str]]) -> None:
        super().__init__(line_edit)
        self._matches = matches
        self.suggestions = QStringListModel(self)
        self.completer = QCompleter(self.suggestions, self)
        self.completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        line_edit.setCompleter(self.completer)
        line_edit.textEdited.connect(self.suggest)
        self.activated = self.completer.activated

    def suggest(self, text: str) -> None:
        names = self._matches(text)
        self.suggestions.setStringList(names)
        if names:
            self.completer.complete()
        else:
            self.completer.popup().hide()
