"""Business rules for categories."""

from __future__ import annotations

import dataclasses
import sqlite3
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from nodus.database.database import Database
from nodus.database.repositories.category_repository import CategoryRepository
from nodus.models.category import Category
from nodus.models.payee import normalize_name
from nodus.models.transaction import TransactionType
from nodus.services.errors import (
    ValidationError,
    clean_name,
    require_found,
    require_unique_name,
)
from nodus.services.sorting import name_sort_key

DUPLICATE_TEXT = "Ya existe una categoría con ese nombre."


@dataclass(frozen=True)
class CategoryNode:
    """A top-level category with its subcategories, in display order."""

    category: Category
    children: list[Category]


class CategoryService:
    def __init__(self, database: Database, categories: CategoryRepository) -> None:
        self._database = database
        self._categories = categories

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
        return require_found(self._categories.get(category_id), "La categoría no existe.")

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
        """Deletes a category and its subcategories, moving their transactions to "Otros"."""
        category = self._require_editable(category_id)
        fallback = self._categories.get_system(category.kind)
        subcategory_ids = self._categories.subcategory_ids(category_id)
        with self._database.transaction():
            for doomed_id in [*subcategory_ids, category_id]:
                self._categories.reassign_transactions(doomed_id, fallback.id)
                self._categories.delete(doomed_id)

    def _require_editable(self, category_id: int) -> Category:
        category = self.get(category_id)
        if category.is_fixed:
            raise ValidationError(f"La categoría «{category.name}» no se puede modificar.")
        return category

    def _require_new_name(self, category: Category) -> None:
        """No other category beside it (same kind and parent) has the same name, ignoring
        case and accents: «Cómida» is «Comida»."""
        siblings = (
            other.name
            for other in self._categories.list(category.kind)
            if other.parent_id == category.parent_id and other.id != category.id
        )
        require_unique_name(category.name, siblings, DUPLICATE_TEXT)

    @staticmethod
    def _require_valid_parent(parent: Category, kind: TransactionType) -> None:
        if parent.is_subcategory:
            raise ValidationError(
                "Una subcategoría no puede tener subcategorías.", field="parent_id"
            )
        if parent.is_fixed:
            raise ValidationError(
                f"No se pueden agregar subcategorías a «{parent.name}».", field="parent_id"
            )
        if parent.kind is not kind:
            raise ValidationError(
                "Una subcategoría debe ser del mismo tipo que su categoría.", field="parent_id"
            )

    @staticmethod
    @contextmanager
    def _unique_name() -> Iterator[None]:
        """Turns the database's unique-name violation into a message for the user."""
        try:
            yield
        except sqlite3.IntegrityError as error:
            raise ValidationError(DUPLICATE_TEXT, field="name") from error
