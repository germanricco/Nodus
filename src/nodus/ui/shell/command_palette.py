"""Ctrl+K: one field to reach anything by its name, as Actual and Monarch do.

It finds the pages, what the window does (with its keys, so the palette also teaches
them), and every account, category, payee, tag and goal, which opens its page. With the
field empty it shows the ones used last first (``SettingsService.recent_commands``).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import partial

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QKeyEvent, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QAbstractItemView, QDialog, QLineEdit, QVBoxLayout, QWidget

from nodus.i18n import N_, _
from nodus.models.names import normalize_name
from nodus.services.container import Services
from nodus.ui.navigation import DetailId, PageId, RecordLink
from nodus.ui.shortcuts import NEXT_ROW, OPEN_ROW, PREVIOUS_ROW, page_keys
from nodus.ui.theme.design import Layout, Space
from nodus.ui.widgets.tables.table import record_table

PAGE = N_("Página")
ACTION = N_("Acción")
KIND_OF_RECORD = {
    DetailId.ACCOUNT: N_("Cuenta"),
    DetailId.CATEGORY: N_("Categoría"),
    DetailId.PAYEE: N_("Beneficiario"),
    DetailId.TAG: N_("Etiqueta"),
    DetailId.GOAL: N_("Meta"),
}
TITLE, KIND, KEYS = range(3)


@dataclass(frozen=True)
class Command:
    """Something the palette offers: ``key`` names it among the recent ones."""

    key: str
    title: str
    kind: str  # translated
    run: Callable[[], None]
    keys: str = ""


def page_commands(open_page: Callable[[PageId], None]) -> list[Command]:
    keys = page_keys()
    return [
        Command(
            f"page:{page_id.name}",
            page_id.label,
            _(PAGE),
            lambda p=page_id: open_page(p),
            keys.get(page_id, ""),
        )
        for page_id in PageId
    ]


def record_commands(services: Services, open_record: Callable[[RecordLink], None]) -> list[Command]:
    """Every account, category, payee, tag and goal in use, each leading to its page."""
    records = [
        *((DetailId.ACCOUNT, a.id, a.name) for a in services.accounts.list_accounts()),
        *((DetailId.CATEGORY, c.id, c.name) for c in services.categories.list_categories()),
        *((DetailId.PAYEE, p.id, p.name) for p in services.payees.list_payees()),
        *((DetailId.TAG, t.id, t.name) for t in services.tags.list_tags()),
        *((DetailId.GOAL, g.id, g.name) for g in services.goals.list_goals() if not g.is_archived),
    ]
    return [
        Command(
            f"{detail.name.lower()}:{item_id}",
            name,
            _(KIND_OF_RECORD[detail]),
            partial(open_record, RecordLink(detail, item_id)),
        )
        for detail, item_id, name in records
        if item_id is not None
    ]


def matching(commands: Sequence[Command], query: str, recent: Sequence[str]) -> list[Command]:
    """The commands whose name or kind has every word of ``query``, accents and case
    aside: those whose name starts with it first, then the recent ones, then the rest in
    their order. With no query, the recent ones and then every page and action."""
    words = normalize_name(query).split()
    rank_of_recent = {key: rank for rank, key in enumerate(recent)}
    if not words:
        by_key = {command.key: command for command in commands}
        firsts = [by_key[key] for key in recent if key in by_key]
        rest = [c for c in commands if c.kind in (_(PAGE), _(ACTION)) and c not in firsts]
        return firsts + rest

    def found(command: Command) -> bool:
        text = normalize_name(f"{command.title} {command.kind}")
        return all(word in text for word in words)

    def rank(item: tuple[int, Command]) -> tuple[bool, int, int]:
        index, command = item
        starts = normalize_name(command.title).startswith(" ".join(words))
        return not starts, rank_of_recent.get(command.key, len(recent)), index

    hits = [(index, command) for index, command in enumerate(commands) if found(command)]
    return [command for _index, command in sorted(hits, key=rank)]


class CommandPalette(QDialog):
    """The field and, under it, what matches; ↑ and ↓ choose, Enter runs it and Esc or a
    click outside closes it."""

    def __init__(
        self,
        commands: Sequence[Command],
        recent: Sequence[str],
        on_run: Callable[[Command], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("CommandPalette")
        self.setAccessibleName(_("Ir a…"))
        self._commands = list(commands)
        self._recent = list(recent)
        self._on_run = on_run
        self._shown: list[Command] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Space.M, Space.M, Space.M, Space.M)
        layout.setSpacing(Space.S)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(_("Ir a una página, una cuenta, una categoría…"))
        self.search_input.setAccessibleName(_("Ir a…"))
        self.search_input.textChanged.connect(self._fill)
        self.search_input.installEventFilter(self)
        layout.addWidget(self.search_input)
        self.model = QStandardItemModel(0, 3, self)
        self.table = record_table(self.model, TITLE)
        self.table.horizontalHeader().hide()
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # the keys stay in the field
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.clicked.connect(self._run_index)
        layout.addWidget(self.table)
        self.setFixedWidth(Layout.PALETTE_WIDTH)
        self._fill("")

    @property
    def shown(self) -> list[Command]:
        return list(self._shown)

    def open_over(self, window: QWidget) -> None:
        """Opens centered across ``window``, near its top, ready to type in."""
        top_left = window.mapToGlobal(window.rect().topLeft())
        x = top_left.x() + (window.width() - self.width()) // 2
        self.move(x, top_left.y() + Layout.PALETTE_TOP)
        self.show()
        self.search_input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _fill(self, query: str) -> None:
        self._shown = matching(self._commands, query, self._recent)
        self.model.removeRows(0, self.model.rowCount())
        for command in self._shown:
            keys = QStandardItem(command.keys)
            keys.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.model.appendRow([QStandardItem(command.title), QStandardItem(command.kind), keys])
        if self._shown:
            self.table.selectRow(0)
        # As tall as what it found, up to a few rows; the rest scrolls.
        rows = min(len(self._shown), Layout.PALETTE_ROWS)
        self.table.setVisible(rows > 0)
        self.table.setFixedHeight(rows * self.table.verticalHeader().defaultSectionSize())
        self.adjustSize()

    def _move(self, step: int) -> None:
        if not self._shown:
            return
        current = self.table.currentIndex().row()
        row = min(max(current + step, 0), len(self._shown) - 1)
        self.table.selectRow(row)

    def run_chosen(self) -> None:
        row = self.table.currentIndex().row()
        if 0 <= row < len(self._shown):
            self._run(self._shown[row])

    def _run_index(self, index: QModelIndex) -> None:
        self._run(self._shown[index.row()])

    def _run(self, command: Command) -> None:
        self.close()
        self._on_run(command)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if isinstance(event, QKeyEvent) and event.type() == QKeyEvent.Type.KeyPress:
            if PREVIOUS_ROW.matches(event) or NEXT_ROW.matches(event):
                self._move(-1 if PREVIOUS_ROW.matches(event) else 1)
                return True
            if OPEN_ROW.matches(event):
                self.run_chosen()
                return True
        return False
