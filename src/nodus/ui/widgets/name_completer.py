"""Suggestions of existing names under a text field, as payees and tags use them."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, QStringListModel, Qt, QTimer
from PySide6.QtGui import QFocusEvent
from PySide6.QtWidgets import QCompleter, QLineEdit

from nodus.ui.widgets.combo_box import style_as_list_popup


class NameCompleter(QObject):
    """Shows under ``line_edit`` the names ``matches`` returns for what is typed.

    The matching ignores case and accents and also finds names by their middle, which
    QCompleter's own filter cannot do, so the list is rebuilt on every keystroke and shown
    unfiltered. ``activated`` is the completer's: it carries the chosen name.

    With ``suggest_on_focus``, an empty field also suggests when it is clicked or reached
    with Tab, asking ``matches`` for an empty text: what to offer before typing.
    """

    # Reaching the field by itself, not focus coming back as a popup closes or the
    # window opens, which would reopen the list the user just closed.
    _USER_FOCUS = (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason)

    def __init__(
        self,
        line_edit: QLineEdit,
        matches: Callable[[str], list[str]],
        suggest_on_focus: bool = False,
    ) -> None:
        super().__init__(line_edit)
        self._matches = matches
        self._line_edit = line_edit
        self.suggestions = QStringListModel(self)
        self.completer = QCompleter(self.suggestions, self)
        self.completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        style_as_list_popup(self.completer.popup())
        line_edit.setCompleter(self.completer)
        line_edit.textEdited.connect(self.suggest)
        self.activated = self.completer.activated
        if suggest_on_focus:
            line_edit.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Suggests in an empty field clicked or reached with Tab."""
        reached = event.type() == QEvent.Type.MouseButtonPress or (
            isinstance(event, QFocusEvent)
            and event.gotFocus()
            and event.reason() in self._USER_FOCUS
        )
        if reached and not self._line_edit.text().strip():
            self.suggest("")
        return super().eventFilter(watched, event)

    def suggest(self, text: str) -> None:
        names = self._matches(text)
        self.suggestions.setStringList(names)
        if names:
            self.completer.complete()
            # After the line edit's own complete(), which follows each key and resizes it.
            QTimer.singleShot(0, self, lambda: self._fit_height(len(names)))
        else:
            self.completer.popup().hide()

    def _fit_height(self, count: int) -> None:
        """Makes the list as tall as its options (up to ``maxVisibleItems``): QCompleter
        sizes it without the ListPopup padding, which left a scroll bar on short lists."""
        popup = self.completer.popup()
        if not popup.isVisible():
            return
        rows = min(count, self.completer.maxVisibleItems())
        chrome = popup.height() - popup.viewport().height()
        popup.resize(popup.width(), sum(popup.sizeHintForRow(i) for i in range(rows)) + chrome)
