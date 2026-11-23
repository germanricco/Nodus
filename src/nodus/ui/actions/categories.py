"""Deleting a category, from the list in Categorías or from a category's page."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from nodus.i18n import _, ngettext
from nodus.models.category import Category
from nodus.services.container import Services
from nodus.ui.dialogs.confirm import delete_with_confirm
from nodus.ui.event_bus import EventBus


def category_delete_warning(services: Services, category: Category) -> str:
    """What deleting ``category`` takes with it: its subcategories, and where its
    movements go."""
    has_children = any(
        node.category.id == category.id and node.children
        for node in services.categories.category_tree(category.kind)
    )
    if has_children:
        deletion = _("Se va a eliminar «{name}» y sus subcategorías.")
    else:
        deletion = _("Se va a eliminar «{name}».")
    count = services.categories.transaction_count(category.id)
    if count == 0:
        consequence = _("No tiene transacciones.")
    else:
        consequence = ngettext(
            "Su única transacción pasa a «Otros».",
            "Sus {count} transacciones pasan a «Otros».",
            count,
        ).format(count=count)
    return f"{deletion.format(name=category.name)} {consequence}"


def delete_category(
    parent: QWidget, services: Services, event_bus: EventBus, category: Category
) -> bool:
    """Deletes ``category`` once the user confirms; True if it was deleted."""
    return delete_with_confirm(
        parent,
        _("Eliminar categoría"),
        category_delete_warning(services, category),
        lambda: services.categories.delete(category.id),
        event_bus.categories_changed,
        event_bus.transactions_changed,
    )
