"""Persistence of tags and of the tags of each transaction."""

from __future__ import annotations

import dataclasses
import sqlite3
from collections import defaultdict
from collections.abc import Iterable

from nodus.database.repositories.base import Repository
from nodus.models.tag import Tag


class TagRepository(Repository):
    def add(self, tag: Tag) -> Tag:
        tag_id = self._insert(
            "INSERT INTO tags (name, normalized_name, color) VALUES (?, ?, ?)",
            (tag.name, tag.normalized_name, tag.color),
        )
        return dataclasses.replace(tag, id=tag_id)

    def update(self, tag: Tag) -> None:
        self._execute(
            "UPDATE tags SET name = ?, normalized_name = ?, color = ? WHERE id = ?",
            (tag.name, tag.normalized_name, tag.color, tag.id),
        )

    def get(self, tag_id: int) -> Tag | None:
        row = self._fetch_one("SELECT * FROM tags WHERE id = ?", (tag_id,))
        return self._from_row(row) if row else None

    def find_by_normalized(self, normalized: str) -> Tag | None:
        row = self._fetch_one("SELECT * FROM tags WHERE normalized_name = ?", (normalized,))
        return self._from_row(row) if row else None

    def list(self) -> list[Tag]:
        return [self._from_row(row) for row in self._fetch_all("SELECT * FROM tags")]

    def delete(self, tag_id: int) -> None:
        self._execute("DELETE FROM tags WHERE id = ?", (tag_id,))

    def tags_for(self, transaction_ids: Iterable[int]) -> dict[int, list[Tag]]:
        """The tags of each of ``transaction_ids``, by name; ids without tags are left out."""
        ids = list(transaction_ids)
        found: dict[int, list[Tag]] = defaultdict(list)
        # SQLite caps the parameters of one statement, so long lists go in chunks.
        for start in range(0, len(ids), 500):
            chunk = ids[start : start + 500]
            rows = self._fetch_all(
                "SELECT tt.transaction_id, g.* FROM transaction_tags tt"
                " JOIN tags g ON g.id = tt.tag_id"
                f" WHERE tt.transaction_id IN ({', '.join('?' * len(chunk))})"
                " ORDER BY g.normalized_name",
                chunk,
            )
            for row in rows:
                found[row["transaction_id"]].append(self._from_row(row))
        return dict(found)

    def set_for(self, transaction_id: int, tag_ids: Iterable[int]) -> None:
        """Replaces the tags of ``transaction_id`` with ``tag_ids``."""
        self._execute("DELETE FROM transaction_tags WHERE transaction_id = ?", (transaction_id,))
        self._database.connection.executemany(
            "INSERT INTO transaction_tags (transaction_id, tag_id) VALUES (?, ?)",
            [(transaction_id, tag_id) for tag_id in dict.fromkeys(tag_ids)],
        )

    def count_transactions(self, tag_id: int) -> int:
        row = self._fetch_one("SELECT COUNT(*) FROM transaction_tags WHERE tag_id = ?", (tag_id,))
        return row[0]

    def reassign(self, source_id: int, target_id: int) -> None:
        """Gives ``target_id`` to every transaction tagged ``source_id``, which loses it."""
        self._execute(
            "INSERT OR IGNORE INTO transaction_tags (transaction_id, tag_id)"
            " SELECT transaction_id, ? FROM transaction_tags WHERE tag_id = ?",
            (target_id, source_id),
        )
        self._execute("DELETE FROM transaction_tags WHERE tag_id = ?", (source_id,))

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Tag:
        return Tag(id=row["id"], name=row["name"], color=row["color"])
