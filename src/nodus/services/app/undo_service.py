"""Undoing the actions that change data without asking first (principle 4, recovery).

Deleting asks before and is never undone.
What is undone is what runs on one click: skipping or paying a recurring charge,
paying off installments, editing several transactions, merging payees or tags. Each
of those actions leaves an ``UndoRecord`` here, built in the same database
transaction from what was there before, and the interface offers «Deshacer».
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from nodus.database.database import Database
from nodus.services.errors import ValidationError


class UndoError(ValidationError):
    """An action can no longer be undone: what it changed changed again since, or it was
    already undone. The message says which, for the user."""


def changed_since(what: str) -> UndoError:
    """The error for data edited after the action: undoing it would lose that edit."""
    return UndoError(f"{what} cambió después, así que ya no se puede deshacer.")


@dataclass(eq=False)
class UndoRecord:
    """One action that can be undone. ``description`` says what was done («Se omitió
    Internet.») and is the toast's text; ``revert`` puts the data back as it was, after
    checking that what the action left is still there (raising ``UndoError`` if not).
    It runs inside a database transaction, so it is undone whole or not at all."""

    description: str
    revert: Callable[[], None]
    undone: bool = field(default=False, init=False)
    forgotten: bool = field(default=False, init=False)


class UndoService:
    """Keeps the last action of the session that can be undone, for Ctrl+Z, and undoes
    the one a toast offers. One level: undoing does not bring back the one before."""

    def __init__(self, database: Database) -> None:
        self._database = database
        self.last: UndoRecord | None = None
        self._offered: list[UndoRecord] = []

    def offer(self, description: str, revert: Callable[[], None]) -> UndoRecord:
        """Records an action that was just done; the services call it."""
        self.last = UndoRecord(description, revert)
        self._offered.append(self.last)
        return self.last

    def forget(self) -> None:
        """Nothing done before can be undone any more, not even from a toast still on
        screen: the data was replaced by a copy, and undoing would write old changes
        over it."""
        for record in self._offered:
            record.forgotten = True
        self._offered.clear()
        self.last = None

    def undo(self, record: UndoRecord | None = None) -> UndoRecord:
        """Undoes ``record``, or the last action when None, and returns it.

        Raises ``UndoError`` if there is nothing to undo, it was undone already, or its
        data changed since."""
        record = record or self.last
        if record is None:
            raise UndoError("No hay nada para deshacer.")
        if record.undone:
            raise UndoError("Eso ya se deshizo.")
        if record.forgotten:
            raise UndoError("Después de restaurar una copia, eso ya no se puede deshacer.")
        with self._database.transaction():
            record.revert()
        record.undone = True
        if record is self.last:
            self.last = None
        return record
