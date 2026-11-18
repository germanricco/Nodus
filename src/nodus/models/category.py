"""Categories that classify income and expenses."""

from __future__ import annotations

from dataclasses import dataclass

from nodus.i18n import N_, SOURCE_LANGUAGE, _, current_language
from nodus.models.transaction import TransactionType

OTHERS_NAME = N_("Otros")
REFUNDS_NAME = N_("Reembolsos")
# The categories the first migration creates, by the Spanish name it gives them. A new
# database names them in its language (``CategoryService.name_defaults``).
DEFAULT_NAMES = (
    N_("Supermercado y comida"), N_("Vivienda"), N_("Servicios"), N_("Transporte"),
    N_("Salud"), N_("Educación"), N_("Proyectos"), N_("Ocio"), N_("Ropa"), N_("Sueldo"),
    N_("Trabajo freelance"), REFUNDS_NAME,
)  # fmt: skip


def fixed_name(is_system: bool, is_refunds: bool) -> str | None:
    """The name a fixed category shows in another language, whatever the database says:
    it cannot be renamed, so its name is Nodus's. In Spanish, None: the database keeps
    the name, which an older Nodus may have taken from a category the user had renamed.
    """
    if current_language() is SOURCE_LANGUAGE or not (is_system or is_refunds):
        return None
    return _(OTHERS_NAME) if is_system else _(REFUNDS_NAME)


@dataclass(frozen=True)
class Category:
    """A user-defined label for transactions of one kind (income or expense).

    ``parent_id`` makes it a subcategory, which always has its parent's kind. System
    categories ("Otros", one per kind) receive the transactions of deleted categories,
    and ``is_refunds`` marks the income category whose movements can be linked to an
    expense as its refund; neither can be edited or deleted (``is_fixed``).
    """

    id: int | None
    name: str
    kind: TransactionType
    color: str
    parent_id: int | None = None
    is_system: bool = False
    is_refunds: bool = False

    @property
    def is_fixed(self) -> bool:
        """Nodus relies on it, so it cannot be renamed, deleted or given subcategories."""
        return self.is_system or self.is_refunds

    @property
    def is_subcategory(self) -> bool:
        return self.parent_id is not None
