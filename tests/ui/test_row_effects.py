"""Every row action does what its ``Effect`` says, on every page with the demo data:
opening changes nothing, what changes data at once offers «Deshacer» (and Ctrl+Z undoes
it), and what destroys data asks first."""

from datetime import date

import pytest
from demo_data import load_demo_data
from factories import table_rows
from PySide6.QtWidgets import QDialog, QMessageBox
from qt_cleanup import flush_deleted

from nodus.ui.navigation import DetailId, PageId
from nodus.ui.widgets.row_actions import Effect, MoreButton, RowAction, _RowHandler
from nodus.ui.widgets.selectable_table import SelectableTable

ROWS_PER_TABLE = 3  # the first rows of a long list have the same actions as the rest
OPPOSITES = {
    "Archivar": "Desarchivar",
    "Desarchivar": "Archivar",
    "Pausar": "Reanudar",
    "Reanudar": "Pausar",
    "Subir": "Bajar",
    "Bajar": "Subir",
    "Deshacer adelanto": "Adelantar las cuotas que faltan",
}


def page_actions(window) -> list[RowAction]:
    """The actions of every row on the page shown now: «⋯» buttons, rows with a right
    click and the first rows of each table."""
    page = window.current_page
    actions = []
    for source in page.findChildren(MoreButton) + page.findChildren(_RowHandler):
        actions += source.actions_list()
    for table in page.findChildren(SelectableTable):
        for row in range(min(table.model().rowCount(), ROWS_PER_TABLE)):
            actions += table.actions_for(row)
    return actions


def visits(services) -> list[tuple]:
    """Every list page, and the page of an account and of a goal."""
    account = services.accounts.list_accounts()[0]
    goal = services.goals.list_goals()[0]
    return [(page_id,) for page_id in PageId] + [
        (DetailId.ACCOUNT, account.id),
        (DetailId.GOAL, goal.id),
    ]


def go(window, visit: tuple) -> None:
    if len(visit) == 1:
        window.show_page(visit[0])
    else:
        window.show_detail(*visit)
    flush_deleted()  # rows replaced by a refresh are still children until deleted


def stored(database) -> dict:
    """All the user's data but the settings, which remember the page shown."""
    names = database.connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return table_rows(database, *(row[0] for row in names if row[0] != "settings"))


@pytest.fixture
def questions(monkeypatch) -> list[str]:
    """Every dialog an action opens, answered with «Cancelar»."""
    asked = []

    def refuse(dialog) -> int:
        asked.append(dialog.windowTitle())
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", refuse)
    monkeypatch.setattr(QMessageBox, "exec", refuse)
    return asked


def test_every_row_action_does_what_its_effect_says(window, services, database, questions):
    load_demo_data(services, date.today())
    window._event_bus.emit_all()
    checked = {effect: 0 for effect in Effect}
    for visit in visits(services):
        go(window, visit)
        kinds = {(a.text, a.effect): None for a in page_actions(window) if a.enabled}
        for text, effect in kinds:
            # Read again before each run: running one may rebuild the rows.
            go(window, visit)
            action = next(
                a
                for a in page_actions(window)
                if a.enabled and (a.text, a.effect) == (text, effect)
            )
            checked[effect] += 1
            check(window, services, database, questions, action, visit)
    assert all(checked.values()), checked


def check(window, services, database, questions, action, visit) -> None:
    where = f"«{action.text}» on {visit}"
    before = stored(database)
    asked = len(questions)
    last = services.undo.last
    action.callback()
    if action.effect is Effect.OPEN:
        assert stored(database) == before, f"{where} opens, so it changes nothing"
    elif action.effect is Effect.CONFIRMED:
        assert len(questions) > asked, f"{where} asks first"
        assert stored(database) == before, f"{where} changes nothing when refused"
    elif action.effect is Effect.UNDOABLE:
        assert services.undo.last is not last, f"{where} offers «Deshacer»"
        window.undo_last()
        assert stored(database) == before, f"{where} is undone by Ctrl+Z"
    else:
        assert stored(database) != before, f"{where} changes something"
        go(window, visit)
        texts = {a.text for a in page_actions(window)}
        assert OPPOSITES[action.text] in texts, f"{where} can be reversed from the menu"
