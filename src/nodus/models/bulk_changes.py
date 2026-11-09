"""What to change in several transactions at once."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BulkChanges:
    """The fields to change in a group of transactions; what is left empty stays as each
    transaction has it, so one edit can fix the payee of many without touching their
    notes.

    ``payee_name`` works as in ``TransactionDraft``: the payee with that name, or a new one.
    ``add_tags`` and ``remove_tags`` are tag names added to or taken from each transaction,
    keeping its other tags.
    """

    category_id: int | None = None
    payee_name: str = ""
    note: str = ""
    add_tags: tuple[str, ...] = ()
    remove_tags: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (
            self.category_id is not None
            or self.payee_name.strip()
            or self.note.strip()
            or self.add_tags
            or self.remove_tags
        )
