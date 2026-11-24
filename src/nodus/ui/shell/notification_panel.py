"""Popup under the bell that lists the notifications."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from nodus.i18n import N_, _
from nodus.services.app.notification_service import Notice, NoticeKind
from nodus.ui.shell.notices import NOTICES
from nodus.ui.theme.design import Layout, RowRole, Space
from nodus.ui.theme.theme_manager import active_theme
from nodus.ui.widgets.card import card_title
from nodus.ui.widgets.color_dot import ColorDot
from nodus.ui.widgets.empty_state import EmptyState
from nodus.ui.widgets.style import (
    clear_layout,
    muted_label,
    separator,
    set_style_property,
    show_below,
)
from nodus.ui.widgets.tables.row_actions import Effect, RowAction, install_row_actions
from nodus.ui.widgets.tables.row_layout import row_layout, row_lines, row_list

NEWS_LABEL = N_("Qué trae")


class NoticeRow(QWidget):
    """A notice: title and detail, with a dot while the user has not opened it. A click
    does what the notice asks; the right click also offers to put it away."""

    opened = Signal(object)  # Notice
    dismissed = Signal(object)  # Notice
    news_requested = Signal(object)  # Notice

    def __init__(self, notice: Notice) -> None:
        super().__init__()
        self.notice = notice
        layout = row_layout(self, RowRole.DOUBLE)
        # An empty dot once seen, so every title starts at the same place.
        self.dot = ColorDot("" if notice.seen else active_theme().accent, Layout.UNSEEN_DOT)
        layout.addWidget(self.dot)
        texts = row_lines()
        title = QLabel(notice.title)
        title.setWordWrap(True)
        if notice.seen:
            set_style_property(title, "muted", True)
        else:
            title.setObjectName("RowTitle")
        detail = muted_label(notice.detail)
        detail.setWordWrap(True)
        texts.addWidget(title)
        texts.addWidget(detail)
        layout.addLayout(texts, stretch=1)
        self.setAccessibleName(
            notice.title if notice.seen else _("Sin revisar: {title}").format(title=notice.title)
        )
        install_row_actions(self, self.actions, open_on_click=_(NOTICES[notice.kind].action_text))

    def actions(self) -> list[RowAction]:
        notice = self.notice
        behavior = NOTICES[notice.kind]
        result = [
            RowAction(
                _(behavior.action_text),
                lambda: self.opened.emit(notice),
                default=True,
                effect=Effect.OPEN,
            )
        ]
        if notice.kind is NoticeKind.UPDATE and notice.notes:
            result.append(
                RowAction(
                    _(NEWS_LABEL), lambda: self.news_requested.emit(notice), effect=Effect.OPEN
                )
            )
        if behavior.dismiss_text is not None:
            result.append(
                RowAction(
                    _(behavior.dismiss_text),
                    lambda: self.dismissed.emit(notice),
                    # It only puts the notice away: whatever comes next is announced.
                    effect=Effect.TOGGLE,
                )
            )
        return result


class NotificationPanel(QFrame):
    """Lists the notices, the ones not opened yet first and marked with a dot, or says
    there is nothing new.

    A popup: it closes on its own when the user clicks elsewhere, and when a notice is
    opened, since that leads to another page.
    """

    action_requested = Signal(object)  # Notice
    dismiss_requested = Signal(object)  # Notice
    news_requested = Signal(object)  # Notice

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("NotificationPanel")
        self.setFixedWidth(Layout.NOTIFICATION_PANEL_WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Space.M, Space.M, Space.M, Space.M)
        layout.setSpacing(0)
        header = QHBoxLayout()
        header.setContentsMargins(Space.S, 0, Space.S, Space.XS)
        title = card_title(_("Notificaciones"))
        header.addWidget(title)
        header.addStretch()
        self.unseen_label = muted_label("")
        header.addWidget(self.unseen_label)
        layout.addLayout(header)
        self._rows = row_list()
        layout.addLayout(self._rows)
        self.rows: list[NoticeRow] = []

    def set_notices(self, notices: list[Notice]) -> None:
        clear_layout(self._rows)
        self.rows = []
        unseen = sum(1 for notice in notices if not notice.seen)
        self.unseen_label.setText(_("{count} sin revisar").format(count=unseen) if unseen else "")
        if not notices:
            self._rows.addWidget(EmptyState(_("Sin novedades."), compact=True))
        for index, notice in enumerate(notices):
            if index:
                self._rows.addWidget(separator())
            row = NoticeRow(notice)
            row.opened.connect(self._act)
            row.news_requested.connect(self._show_news)
            row.dismissed.connect(self.dismiss_requested)
            self._rows.addWidget(row)
            self.rows.append(row)
        self.adjustSize()

    def open_below(self, anchor: QWidget) -> None:
        """Shows the panel under ``anchor``, its right edge aligned with the anchor's."""
        show_below(self, anchor, align_right=True)

    def _show_news(self, notice: Notice) -> None:
        self.hide()
        self.news_requested.emit(notice)

    def _act(self, notice: Notice) -> None:
        self.hide()
        self.action_requested.emit(notice)
