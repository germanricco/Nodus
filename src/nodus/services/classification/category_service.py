"""Business rules for categories."""

from __future__ import annotations

import dataclasses
import sqlite3
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

from nodus.database.database import Database
from nodus.database.repositories.category_repository import CategoryRepository
from nodus.i18n import N_, _
from nodus.models.category import DEFAULT_NAMES, Category
from nodus.models.names import normalize_name
from nodus.models.transaction import TransactionType
from nodus.services.backups.backup_service import BackupService
from nodus.services.errors import (
    ValidationError,
    clean_name,
    require_found,
    require_unique_name,
)
from nodus.services.sorting import name_sort_key

DUPLICATE_TEXT = N_("Ya existe una categoría con ese nombre.")


@dataclass(frozen=True)
class CategoryNode:
    """A top-level category with its subcategories, in display order."""

    category: Category
    children: list[Category]


class CategoryService:
    """Income and expense categories, with their subcategories and colors."""

    def __init__(
        self, database: Database, categories: CategoryRepository, backups: BackupService
    ) -> None:
        self._database = database
        self._categories = categories
        self._backups = backups

    def name_defaults(self) -> None:
        """Gives the categories the first migration created the names of the language
        Nodus is in. Only for a new database: in one already used, the names are the
        user's, even the ones nobody changed."""
        with self._database.transaction():
            for category in self._categories.list():
                shown = _(category.name)
                if category.name in DEFAULT_NAMES and shown != category.name:
                    self._categories.update(dataclasses.replace(category, name=shown))

    def list_categories(self, kind: TransactionType | None = None) -> list[Category]:
        """Categories in alphabetical order, with the system "Otros" last."""
        return sorted(
            self._categories.list(kind), key=lambda c: (c.is_system, name_sort_key(c.name))
        )

    def category_tree(self, kind: TransactionType) -> list[CategoryNode]:
        """Top-level categories of ``kind``, each with its subcategories; "Otros" last."""
        categories = self.list_categories(kind)
        children: dict[int, list[Category]] = defaultdict(list)
        for category in categories:
            if category.is_subcategory:
                children[category.parent_id].append(category)
        return [
            CategoryNode(category, children[category.id])
            for category in categories
            if not category.is_subcategory
        ]

    def transaction_count(self, category_id: int) -> int:
        """Transactions in the category and its subcategories: what deleting it would move."""
        ids = [category_id, *self._categories.subcategory_ids(category_id)]
        return self._categories.count_transactions(ids)

    def refunds_category(self) -> Category:
        """The income category whose movements can be linked to an expense as its refund."""
        return self._categories.get_refunds()

    def get(self, category_id: int) -> Category:
        return require_found(self._categories.get(category_id), _("La categoría no existe."))

    def create(
        self, name: str, kind: TransactionType, color: str, parent_id: int | None = None
    ) -> Category:
        if parent_id is not None:
            self._require_valid_parent(self.get(parent_id), kind)
        category = Category(None, clean_name(name), kind, color, parent_id)
        self._require_new_name(category)
        with self._unique_name(), self._database.transaction():
            return self._categories.add(category)

    def update(self, category_id: int, name: str, color: str) -> None:
        """Renames or recolors a category.

        Its kind cannot change, since its transactions depend on it.
        """
        category = self._require_editable(category_id)
        updated = dataclasses.replace(category, name=clean_name(name), color=color)
        if normalize_name(updated.name) != normalize_name(category.name):
            self._require_new_name(updated)
        with self._unique_name(), self._database.transaction():
            self._categories.update(updated)

    def delete(self, category_id: int) -> None:
        """Deletes a category and its subcategories, moving their transactions to "Otros".
        The data is copied first, and the copy kept for a month."""
        category = self._require_editable(category_id)
        self._backups.create_before_delete(datetime.now())
        fallback = self._categories.get_system(category.kind)
        subcategory_ids = self._categories.subcategory_ids(category_id)
        with self._database.transaction():
            for doomed_id in [*subcategory_ids, category_id]:
                self._categories.reassign_transactions(doomed_id, fallback.id)
                self._categories.delete(doomed_id)

    def merge_targets(self, category_id: int) -> list[Category]:
        """What ``category_id`` can join: the other categories of its kind that the user
        manages, in display order, none of them its own subcategory."""
        category = self.get(category_id)
        return [
            other
            for node in self.category_tree(category.kind)
            for other in (node.category, *node.children)
            if other.id != category.id and other.parent_id != category.id and not other.is_fixed
        ]

    def can_merge(self, category_id: int) -> bool:
        """Whether ``category_id`` can join another: one the user manages, without
        subcategories (they would go with it) and with somewhere to go."""
        category = self.get(category_id)
        return (
            not category.is_fixed
            and not self._categories.subcategory_ids(category_id)
            and bool(self.merge_targets(category_id))
        )

    def merge(self, source_id: int, target_id: int) -> None:
        """Moves the movements and recurring charges of ``source_id`` to ``target_id``, and
        the payees that had it by default, then deletes it: deleting it, but into the
        category the user chose instead of «Otros». The data is copied first, as for a
        delete."""
        source = self._require_editable(source_id)
        if self._categories.subcategory_ids(source_id):
            raise ValidationError(_("Primero une o elimina sus subcategorías."))
        if target_id not in {c.id for c in self.merge_targets(source_id)}:
            raise ValidationError(_("Elige otra categoría del mismo tipo para unir."))
        self._backups.create_before_delete(datetime.now())
        with self._database.transaction():
            self._categories.reassign_transactions(source.id, target_id)
            self._categories.reassign_payee_defaults(source.id, target_id)
            self._categories.delete(source.id)

    def _require_editable(self, category_id: int) -> Category:
        category = self.get(category_id)
        if category.is_fixed:
            raise ValidationError(
                _("La categoría «{category}» no se puede modificar.").format(category=category.name)
            )
        return category

    def _require_new_name(self, category: Category) -> None:
        """No other category beside it (same kind and parent) has the same name, ignoring
        case and accents: «Cómida» is «Comida»."""
        siblings = (
            other.name
            for other in self._categories.list(category.kind)
            if other.parent_id == category.parent_id and other.id != category.id
        )
        require_unique_name(category.name, siblings, _(DUPLICATE_TEXT))

    @staticmethod
    def _require_valid_parent(parent: Category, kind: TransactionType) -> None:
        if parent.is_subcategory:
            raise ValidationError(
                _("Una subcategoría no puede tener subcategorías."), field="parent_id"
            )
        if parent.is_fixed:
            raise ValidationError(
                _("No se pueden agregar subcategorías a «{parent}».").format(parent=parent.name),
                field="parent_id",
            )
        if parent.kind is not kind:
            raise ValidationError(
                _("Una subcategoría debe ser del mismo tipo que su categoría."), field="parent_id"
            )

    @staticmethod
    @contextmanager
    def _unique_name() -> Iterator[None]:
        """Turns the database's unique-name violation into a message for the user."""
        try:
            yield
        except sqlite3.IntegrityError as error:
            raise ValidationError(_(DUPLICATE_TEXT), field="name") from error
