"""Business rules for tags: unique names, merging and what each one adds up to."""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

from nodus.database.database import Database
from nodus.database.repositories.tag_repository import TagRepository
from nodus.i18n import N_, _
from nodus.models.money import Money
from nodus.models.tag import Tag
from nodus.models.transaction import Transaction
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.accounts.exchange_rate_service import ExchangeRateService
from nodus.services.app.undo_service import UndoService
from nodus.services.classification.named_records import NamedRecordService
from nodus.services.conversion import net_in_pesos
from nodus.services.errors import clean_name, require_free_name
from nodus.services.sorting import name_sort_key, rank_matches
from nodus.services.transactions.transaction_service import TransactionService


@dataclass(frozen=True)
class TagSummary:
    """A tag with its transactions added up, for the tags page. ``net`` is income minus
    expenses in pesos, as for payees; ``unconverted`` counts the dollar movements left out
    for lack of a rate. ``first_on`` and ``last_on`` are the dates of its first and latest
    transactions (None while it has none)."""

    tag: Tag
    count: int
    net: Money
    unconverted: int
    first_on: date | None
    last_on: date | None


class TagService(NamedRecordService[Tag]):
    """Tags: their colors, suggestions while typing, and what each one adds up to."""

    NOT_FOUND_TEXT = N_("La etiqueta no existe.")
    NO_OTHER_TEXT = N_("Elige otra etiqueta para unir.")
    NAME_TAKEN_TEXT = N_("Ya hay otra etiqueta «{name}», así que no se puede deshacer.")

    def __init__(
        self,
        database: Database,
        tags: TagRepository,
        transactions: TransactionService,
        exchange_rates: ExchangeRateService,
        undo: UndoService,
    ) -> None:
        super().__init__(database, tags)
        self._tags = tags
        self._undo = undo
        self._transactions = transactions
        self._exchange_rates = exchange_rates

    def list_tags(self) -> list[Tag]:
        """Every tag in alphabetical order."""
        return self._sorted()

    def any_new(self, names: Iterable[str]) -> bool:
        """Whether saving ``names`` creates a tag, so the lists of tags need refreshing."""
        return any(self.find(name) is None for name in names)

    def matches(self, text: str) -> list[Tag]:
        """Tags whose name contains ``text``, those starting with it first."""
        return rank_matches(self._tags.list(), text)

    def next_color(self) -> str:
        """The color a new tag starts with, unless one is chosen."""
        return self._tags.next_color()

    def create(self, name: str, color: str | None = None) -> Tag:
        """A new tag; without ``color``, the next preset one."""
        color = color or self.next_color()
        tag = self._checked(Tag(None, clean_name(name), color))
        with self._database.transaction():
            return self._tags.add(tag)

    def update(self, tag_id: int, name: str, color: str) -> None:
        tag = self._checked(
            dataclasses.replace(self.get(tag_id), name=clean_name(name), color=color)
        )
        with self._database.transaction():
            self._tags.update(tag)

    def transaction_count(self, tag_id: int) -> int:
        return self._tags.count_transactions(tag_id)

    def tagged_count(self, tag_ids: list[int]) -> int:
        """How many transactions carry at least one of ``tag_ids``."""
        return self._tags.count_tagged(tag_ids)

    def _affected(self, tag_ids: list[int]) -> int:
        """Deleting tags takes them off their transactions."""
        return self.tagged_count(tag_ids)

    def merge_many(self, source_ids: list[int], target_id: int) -> None:
        """Gives ``target_id`` to the transactions tagged with any of ``source_ids`` and
        deletes the sources, all together. It can be undone."""
        sources, target = self._merge_parties(source_ids, target_id)
        rows = [self._tags.row(source.id) for source in sources]
        tagged = [self._tags.tagged(source.id) for source in sources]
        target_had = self._tags.tagged(target_id)
        with self._database.transaction():
            for source in sources:
                self._tags.reassign(source.id, target_id)
                self._tags.delete(source.id)
        merged = self._tags.get(target_id)
        self._undo.offer(
            _("Se unieron {count} etiquetas en {target}.").format(
                count=len(sources) + 1, target=target.name
            ),
            lambda: self._unmerge(target, merged, rows, tagged, target_had),
        )

    def _unmerge(
        self,
        target: Tag,
        merged: Tag | None,
        rows: list[dict[str, Any]],
        tagged: list[set[int]],
        target_had: set[int],
    ) -> None:
        """Undoes ``merge_many``: the merged tags back, with their own id and their
        transactions, and the target only where it was before."""
        self._require_restorable(target, merged, rows, tagged, self._tags.tagged(target.id))
        for row, transaction_ids in zip(rows, tagged, strict=True):
            self._tags.put_back(row)
            self._tags.link(transaction_ids, row["id"])
        self._tags.unlink(set().union(*tagged) - target_had, target.id)

    def summaries(self) -> list[TagSummary]:
        """Every tag with its totals, the most used first."""
        transactions = self._transactions.list_transactions(TransactionFilter(is_transfer=False))
        tags_by_transaction = self._tags.tags_for(t.id for t in transactions)
        by_tag: dict[int, list[Transaction]] = defaultdict(list)
        for transaction in transactions:
            for tag in tags_by_transaction.get(transaction.id, []):
                by_tag[tag.id].append(transaction)
        summaries = [self._summary(tag, by_tag[tag.id]) for tag in self._tags.list()]
        return sorted(summaries, key=lambda s: (-s.count, name_sort_key(s.tag.name)))

    def summary(self, tag_id: int) -> TagSummary:
        """One tag with its totals, for its own page."""
        tag = self.get(tag_id)
        tagged = self._transactions.list_transactions(
            TransactionFilter(tag_id=tag_id, is_transfer=False)
        )
        return self._summary(tag, tagged)

    def _summary(self, tag: Tag, tagged: list[Transaction]) -> TagSummary:
        net, unconverted = net_in_pesos(tagged, self._exchange_rates)
        dates = [t.occurred_on for t in tagged]
        return TagSummary(
            tag, len(tagged), net, unconverted, min(dates, default=None), max(dates, default=None)
        )

    def _checked(self, tag: Tag) -> Tag:
        """``tag`` if its name is usable and no other tag has it."""
        hint = _("; para juntarlas usa «Unir con…»") if tag.id is not None else ""
        require_free_name(
            tag.id,
            tag.normalized_name,
            self._tags.find_by_normalized,
            lambda name: _("Ya existe «{name}»{hint}.").format(name=name, hint=hint),
        )
        return tag
