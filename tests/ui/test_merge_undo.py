"""Merging runs on one click with no question, so every merge offers «Deshacer», and
undoing it leaves the data as it was (principle 4, recovery)."""

from datetime import date

import pytest
from demo_data import load_demo_data
from factories import table_rows
from PySide6.QtCore import Qt

from nodus.ui.dialogs.category_dialog import MergeCategoryDialog
from nodus.ui.dialogs.merge_dialog import MergeDialog
from nodus.ui.dialogs.payee_dialogs import MergePayeeDialog
from nodus.ui.dialogs.tag_dialogs import MergeTagDialog


def two_categories(services):
    """Two categories of one kind that can merge, both with movements."""
    used = [c for c in services.categories.list_categories() if services.categories.can_merge(c.id)]
    kind = used[0].kind
    return [c for c in used if c.kind is kind and services.categories.transaction_count(c.id)][:2]


MERGES = {
    MergeCategoryDialog: two_categories,
    MergePayeeDialog: lambda services: services.payees.list_payees()[:2],
    MergeTagDialog: lambda services: services.tags.list_tags()[:2],
}


def stored(database) -> dict:
    """All the user's data but the settings."""
    names = database.connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return table_rows(database, *(row[0] for row in names if row[0] != "settings"))


def test_every_merge_dialog_is_checked():
    assert set(MergeDialog.__subclasses__()) == set(MERGES)


@pytest.mark.parametrize("dialog_class", list(MERGES), ids=lambda c: c.__name__)
def test_a_merge_is_undone_whole(qtbot, services, event_bus, database, dialog_class):
    load_demo_data(services, date.today())
    items = MERGES[dialog_class](services)
    assert len(items) == 2
    before = stored(database)
    last = services.undo.last
    dialog = dialog_class(services, event_bus, items)
    qtbot.addWidget(dialog)

    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

    assert stored(database) != before
    assert services.undo.last is not last, "the merge offers «Deshacer»"
    services.undo.undo()
    assert stored(database) == before
