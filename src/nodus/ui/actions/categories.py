"""Deleting categories, from the list in Categorías or from a category's page."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from nodus.i18n import _, ngettext
from nodus.models.category import Category
from nodus.services.container import Services
from nodus.ui.dialogs.confirm import delete_with_confirm
from nodus.ui.event_bus import EventBus


def category_delete_warning(services: Services, categories: list[Category]) -> str:
    """What deleting ``categories`` takes with it: their subcategories, and where their
    movements go."""
    with_children = {
        node.category.id
        for kind in {c.kind for c in categories}
        for node in services.categories.category_tree(kind)
        if node.children
    }
    has_children = any(c.id in with_children for c in categories)
    if len(categories) == 1:
        if has_children:
            deletion = _("Se va a eliminar «{name}» y sus subcategorías.")
        else:
            deletion = _("Se va a eliminar «{name}».")
    elif has_children:
        deletion = _("Se van a eliminar {count} categorías y sus subcategorías.")
    else:
        deletion = _("Se van a eliminar {count} categorías.")
    count = services.categories.transactions_in([c.id for c in categories])
    if len(categories) == 1:
        consequence = (
            ngettext(
                "Su única transacción pasa a «Otros».",
                "Sus {count} transacciones pasan a «Otros».",
                count,
            )
            if count
            else _("No tiene transacciones.")
        )
    else:
        consequence = (
            ngettext(
                "Entre todas tienen una transacción, que pasa a «Otros».",
                "Entre todas tienen {count} transacciones, que pasan a «Otros».",
                count,
            )
            if count
            else _("Ninguna tiene transacciones.")
        )
    names = deletion.format(name=categories[0].name, count=len(categories))
    return f"{names} {consequence.format(count=count)}"


def delete_categories(
    parent: QWidget, services: Services, event_bus: EventBus, categories: list[Category]
) -> bool:
    """Deletes ``categories`` once the user confirms; True if they were deleted."""
    title = (
        _("Eliminar categoría")
        if len(categories) == 1
        else _("Eliminar {count} categorías").format(count=len(categories))
    )
    return delete_with_confirm(
        parent,
        title,
        category_delete_warning(services, categories),
        lambda: services.categories.delete_many([c.id for c in categories]),
        event_bus.categories_changed,
        event_bus.transactions_changed,
    )
