"""What payees and tags share: records with a unique name that movements point to, which
can be found by any spelling, deleted with what points to them, and merged into another."""

from __future__ import annotations

from typing import Any, Generic, Protocol, TypeVar

from nodus.database.database import Database
from nodus.models.names import normalize_name
from nodus.services.app.undo_service import UndoError, changed_since
from nodus.services.errors import ValidationError, require_found
from nodus.services.sorting import name_sort_key


class NamedRecord(Protocol):
    id: int | None
    name: str


R = TypeVar("R", bound=NamedRecord)


class NamedRecordService(Generic[R]):
    """The common part of the payee and tag services. A subclass names its texts and says
    how many movements a deletion touches (``_affected``)."""

    NOT_FOUND_TEXT = ""  # "El beneficiario no existe."
    NO_OTHER_TEXT = ""  # asked to merge a record into itself alone
    NAME_TAKEN_TEXT = ""  # undoing a merge finds the name taken; {name} is replaced

    def __init__(self, database: Database, records: Any) -> None:
        self._database = database
        self._records = records

    def get(self, record_id: int) -> R:
        return require_found(self._records.get(record_id), self.NOT_FOUND_TEXT)

    def find(self, name: str) -> R | None:
        """The record called ``name``, ignoring case, accents and signs."""
        normalized = normalize_name(name)
        return self._records.find_by_normalized(normalized) if normalized else None

    def delete(self, record_id: int) -> int:
        """Deletes the record and returns how many movements pointed to it."""
        return self.delete_many([record_id])

    def delete_many(self, record_ids: list[int]) -> int:
        """Deletes every one of ``record_ids`` together, or none if one is missing, and
        returns how many movements pointed to any of them."""
        for record_id in record_ids:
            self.get(record_id)
        count = self._affected(record_ids)
        with self._database.transaction():
            for record_id in record_ids:
                self._records.delete(record_id)
        return count

    def merge(self, source_id: int, target_id: int) -> None:
        """Merges ``source_id`` into ``target_id``, as ``merge_many`` does."""
        self.merge_many([source_id], target_id)

    def merge_many(self, source_ids: list[int], target_id: int) -> None:
        raise NotImplementedError

    def _sorted(self) -> list[R]:
        """Every record in alphabetical order."""
        return sorted(self._records.list(), key=lambda r: name_sort_key(r.name))

    def _affected(self, record_ids: list[int]) -> int:
        raise NotImplementedError

    def _merge_parties(self, source_ids: list[int], target_id: int) -> tuple[list[R], R]:
        """The records to merge, the target left out, and the target; both must exist."""
        sources = [self.get(source_id) for source_id in source_ids if source_id != target_id]
        if not sources:
            raise ValidationError(self.NO_OTHER_TEXT)
        return sources, self.get(target_id)

    def _require_restorable(
        self, target: R, merged: R | None, rows: list[dict], moved: list[set[int]], held: set[int]
    ) -> None:
        """Before undoing a merge: the target is as the merge left it, no record took a
        merged name since, and the target still ``held`` every movement ``moved`` to it."""
        if self._records.get(target.id) != merged:
            raise changed_since(f"«{target.name}»")
        for row, transaction_ids in zip(rows, moved, strict=True):
            if self._records.find_by_normalized(row["normalized_name"]) is not None:
                raise UndoError(self.NAME_TAKEN_TEXT.format(name=row["name"]))
            if not set(transaction_ids) <= held:
                raise changed_since(f"Algún movimiento de «{row['name']}»")
