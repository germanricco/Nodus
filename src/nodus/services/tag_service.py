"""Business rules for tags: unique names, merging and what each one adds up to."""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from dataclasses import dataclass

from nodus.database.database import Database
from nodus.database.repositories.tag_repository import TagRepository
from nodus.database.repositories.transaction_repository import TransactionFilter
from nodus.models.money import Money
from nodus.models.palette import palette_color
from nodus.models.payee import normalize_name
from nodus.models.tag import Tag
from nodus.models.transaction import Transaction
from nodus.services.dashboard_service import net_in_pesos
from nodus.services.errors import ValidationError, clean_name, require_found
from nodus.services.exchange_rate_service import ExchangeRateService
from nodus.services.sorting import name_sort_key, rank_matches
from nodus.services.transaction_service import TransactionService


@dataclass(frozen=True)
class TagSummary:
    """A tag with its transactions added up, for the tags page. ``net`` is income minus
    expenses in pesos, as for payees; ``unconverted`` counts the dollar movements left out
    for lack of a rate."""

    tag: Tag
    count: int
    net: Money
    unconverted: int


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

    def delete(self, tag_id: int) -> int:
        """Deletes a tag, which its transactions lose, and returns how many had it."""
        self.get(tag_id)
        count = self._tags.count_transactions(tag_id)
        with self._database.transaction():
            self._tags.delete(tag_id)
        return count

    def merge(self, source_id: int, target_id: int) -> None:
        """Gives ``target_id`` to the transactions tagged ``source_id`` and deletes the
        latter, for duplicates such as "Viaje" and "Vacaciones"."""
        if source_id == target_id:
            raise ValidationError("Elige otra etiqueta para unir.")
        self.get(source_id)
        self.get(target_id)
        with self._database.transaction():
            self._tags.reassign(source_id, target_id)
            self._tags.delete(source_id)

    def summaries(self) -> list[TagSummary]:
        """Every tag with its totals, the most used first."""
        transactions = self._transactions.list_transactions(TransactionFilter(is_transfer=False))
        tags_by_transaction = self._tags.tags_for(t.id for t in transactions)
        by_tag: dict[int, list[Transaction]] = defaultdict(list)
        for transaction in transactions:
            for tag in tags_by_transaction.get(transaction.id, []):
                by_tag[tag.id].append(transaction)
        summaries = []
        for tag in self._tags.list():
            net, unconverted = net_in_pesos(by_tag[tag.id], self._exchange_rates)
            summaries.append(TagSummary(tag, len(by_tag[tag.id]), net, unconverted))
        return sorted(summaries, key=lambda s: (-s.count, name_sort_key(s.tag.name)))

    def _checked(self, tag: Tag) -> Tag:
        """``tag`` if its name is usable and no other tag has it."""
        if not tag.normalized_name:
            raise ValidationError("El nombre debe tener letras o números.")
        existing = self._tags.find_by_normalized(tag.normalized_name)
        if existing is not None and existing.id != tag.id:
            hint = "; para juntarlas usa «Unir con…»" if tag.id is not None else ""
            raise ValidationError(f"Ya existe «{existing.name}»{hint}.")
        return tag
