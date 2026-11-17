"""The payee and tags of a movement, found by name or created, for every service that saves
movements: one at a time, in installments or several together."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable

from nodus.database.repositories.payee_repository import PayeeRepository
from nodus.database.repositories.tag_repository import TagRepository
from nodus.models.names import normalize_name
from nodus.models.payee import Payee
from nodus.models.tag import Tag
from nodus.models.transaction import Transaction


class MovementLabels:
    """Links movements to payees and tags by the names the user typed.

    Every method runs inside the caller's database transaction, so a save that fails
    leaves no orphan payee or tag behind.
    """

    def __init__(self, payees: PayeeRepository, tags: TagRepository) -> None:
        self._payees = payees
        self._tags = tags

    def with_payee(self, transaction: Transaction, payee_name: str) -> Transaction:
        """``transaction`` linked to the payee called ``payee_name``, creating it if needed;
        without a payee when the name is empty."""
        normalized = normalize_name(payee_name)
        if not normalized:
            return dataclasses.replace(transaction, payee_id=None)
        payee = self._payees.find_by_normalized(normalized) or self._payees.add(
            Payee(None, payee_name.strip())
        )
        return dataclasses.replace(transaction, payee_id=payee.id)

    def set_tags(self, transaction_id: int, names: tuple[str, ...]) -> None:
        """Gives the transaction the tags called ``names``, and no others."""
        self._tags.set_for(transaction_id, self._tag_ids(names))

    def change_tags(
        self, transaction_id: int, added: tuple[str, ...], removed: tuple[str, ...]
    ) -> None:
        """Adds the tags called ``added`` and takes away those called ``removed``, keeping
        the transaction's other tags."""
        dropped = {normalize_name(name) for name in removed}
        current = self._tags.tags_for([transaction_id]).get(transaction_id, [])
        kept = [tag.id for tag in current if normalize_name(tag.name) not in dropped]
        new = [tag_id for tag_id in self._tag_ids(added) if tag_id not in kept]
        self._tags.set_for(transaction_id, kept + new)

    def tag_ids_of(self, transactions: Iterable[Transaction]) -> dict[int, list[int]]:
        """The ids of each transaction's tags, by transaction id."""
        listed = list(transactions)
        found = self._tags.tags_for(t.id for t in listed)
        return {t.id: [tag.id for tag in found.get(t.id, [])] for t in listed}

    def _tag_ids(self, names: tuple[str, ...]) -> list[int]:
        """The tags called ``names``, creating the new ones with the next preset color."""
        tag_ids = []
        for name in names:
            normalized = normalize_name(name)
            if not normalized:
                continue
            tag = self._tags.find_by_normalized(normalized)
            if tag is None:
                tag = self._tags.add(Tag(None, name.strip(), self._tags.next_color()))
            tag_ids.append(tag.id)
        return tag_ids
