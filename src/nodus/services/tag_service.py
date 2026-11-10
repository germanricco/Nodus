"""Business rules for tags: unique names, merging and what each one adds up to."""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from nodus.database.database import Database
from nodus.database.repositories.tag_repository import TagRepository
from nodus.models.money import Money
from nodus.models.palette import palette_color
from nodus.models.payee import normalize_name
from nodus.models.tag import Tag
from nodus.models.transaction import Transaction
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.dashboard_service import net_in_pesos
from nodus.services.errors import ValidationError, clean_name, require_found
from nodus.services.exchange_rate_service import ExchangeRateService
from nodus.services.sorting import name_sort_key, rank_matches
from nodus.services.transaction_service import TransactionService


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


class TagService:
    def __init__(
        self,
        database: Database,
        tags: TagRepository,
        transactions: TransactionService,
        exchange_rates: ExchangeRateService,
    ) -> None:
        self._database = database
        self._tags = tags
        self._transactions = transactions
        self._exchange_rates = exchange_rates

    def list_tags(self) -> list[Tag]:
        """Every tag in alphabetical order."""
        return sorted(self._tags.list(), key=lambda t: name_sort_key(t.name))

    def get(self, tag_id: int) -> Tag:
        return require_found(self._tags.get(tag_id), "La etiqueta no existe.")

    def find(self, name: str) -> Tag | None:
        """The tag called ``name``, ignoring case, accents and signs."""
        normalized = normalize_name(name)
        return self._tags.find_by_normalized(normalized) if normalized else None

    def matches(self, text: str) -> list[Tag]:
        """Tags whose name contains ``text``, those starting with it first."""
        return rank_matches(self._tags.list(), text)

    def create(self, name: str, color: str | None = None) -> Tag:
        """A new tag; without ``color``, the next preset one."""
        color = color or palette_color(len(self._tags.list()))
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

    def delete(self, tag_id: int) -> int:
        """Deletes a tag, which its transactions lose, and returns how many had it."""
        return self.delete_many([tag_id])

    def delete_many(self, tag_ids: list[int]) -> int:
        """Deletes every one of ``tag_ids`` together, or none if one is missing, and
        returns how many transactions had any of them."""
        for tag_id in tag_ids:
            self.get(tag_id)
        count = self.tagged_count(tag_ids)
        with self._database.transaction():
            for tag_id in tag_ids:
                self._tags.delete(tag_id)
        return count

    def merge(self, source_id: int, target_id: int) -> None:
        """Gives ``target_id`` to the transactions tagged ``source_id`` and deletes the
        latter, for duplicates such as "Viaje" and "Vacaciones"."""
        self.merge_many([source_id], target_id)

    def merge_many(self, source_ids: list[int], target_id: int) -> None:
        """Gives ``target_id`` to the transactions tagged with any of ``source_ids`` and
        deletes the sources, all together."""
        sources = [self.get(source_id) for source_id in source_ids if source_id != target_id]
        if not sources:
            raise ValidationError("Elige otra etiqueta para unir.")
        self.get(target_id)
        with self._database.transaction():
            for source in sources:
                self._tags.reassign(source.id, target_id)
                self._tags.delete(source.id)

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
        if not tag.normalized_name:
            raise ValidationError("El nombre debe tener letras o números.", field="name")
        existing = self._tags.find_by_normalized(tag.normalized_name)
        if existing is not None and existing.id != tag.id:
            hint = "; para juntarlas usa «Unir con…»" if tag.id is not None else ""
            raise ValidationError(f"Ya existe «{existing.name}»{hint}.", field="name")
        return tag
