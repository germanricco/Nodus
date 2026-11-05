import pytest
from factories import ars, category_id, expense_draft

from nodus.models.transaction import TransactionType
from nodus.services.errors import ValidationError

EXPENSE = TransactionType.EXPENSE
INCOME = TransactionType.INCOME


def names(services, kind):
    return [c.name for c in services.categories.list_categories(kind)]


def test_default_categories_by_kind_with_otros_last(services):
    assert names(services, EXPENSE) == [
        "Educación", "Ocio", "Proyectos", "Ropa", "Salud", "Servicios",
        "Supermercado y comida", "Transporte", "Vivienda", "Otros",
    ]  # fmt: skip
    assert names(services, INCOME) == ["Reembolsos", "Sueldo", "Trabajo freelance", "Otros"]


def test_names_sort_ignoring_accents(services):
    services.categories.create("Árboles", EXPENSE, "#000000")

    assert names(services, EXPENSE)[:2] == ["Árboles", "Educación"]


def test_create_top_level_and_subcategory(services):
    viajes = services.categories.create("Viajes", EXPENSE, "#123456")
    hoteles = services.categories.create("Hoteles", EXPENSE, "#654321", parent_id=viajes.id)

    assert hoteles.parent_id == viajes.id
    assert "Hoteles" in names(services, EXPENSE)


def test_duplicate_name_in_same_level_and_kind_is_rejected(services):
    with pytest.raises(ValidationError, match="Ya existe"):
        services.categories.create("ocio", EXPENSE, "#000000")


def test_same_name_is_allowed_in_other_kind(services):
    services.categories.create("Proyectos", INCOME, "#000000")

    assert "Proyectos" in names(services, INCOME)


@pytest.mark.parametrize(
    ("parent_name", "parent_kind", "child_kind"),
    [("Otros", EXPENSE, EXPENSE), ("Sueldo", INCOME, EXPENSE)],
    ids=["system-parent", "kind-mismatch"],
)
def test_invalid_parent_is_rejected(services, parent_name, parent_kind, child_kind):
    parent_id = category_id(services, parent_name, parent_kind)

    with pytest.raises(ValidationError):
        services.categories.create("Hija", child_kind, "#000000", parent_id=parent_id)


def test_subcategory_cannot_have_children(services):
    viajes = services.categories.create("Viajes", EXPENSE, "#123456")
    hoteles = services.categories.create("Hoteles", EXPENSE, "#654321", parent_id=viajes.id)

    with pytest.raises(ValidationError):
        services.categories.create("Lujo", EXPENSE, "#000000", parent_id=hoteles.id)


def test_update_renames_and_recolors(services):
    ocio = category_id(services, "Ocio", EXPENSE)

    services.categories.update(ocio, "Salidas", "#abcdef")

    updated = services.categories.get(ocio)
    assert (updated.name, updated.color) == ("Salidas", "#abcdef")


def test_system_category_cannot_be_edited_or_deleted(services):
    otros = category_id(services, "Otros", EXPENSE)

    with pytest.raises(ValidationError):
        services.categories.update(otros, "Varios", "#000000")
    with pytest.raises(ValidationError):
        services.categories.delete(otros)


def test_delete_moves_transactions_of_category_and_subcategories_to_otros(services, pesos):
    viajes = services.categories.create("Viajes", EXPENSE, "#123456")
    hoteles = services.categories.create("Hoteles", EXPENSE, "#654321", parent_id=viajes.id)
    in_parent = services.transactions.create(
        expense_draft(services, pesos.id, ars("10"), category_id=viajes.id)
    )
    in_child = services.transactions.create(
        expense_draft(services, pesos.id, ars("20"), category_id=hoteles.id)
    )

    services.categories.delete(viajes.id)

    otros = category_id(services, "Otros", EXPENSE)
    assert services.transactions.get(in_parent.id).category_id == otros
    assert services.transactions.get(in_child.id).category_id == otros
    assert "Viajes" not in names(services, EXPENSE)
    assert "Hoteles" not in names(services, EXPENSE)


def test_category_tree_nests_subcategories(services):
    viajes = services.categories.create("Viajes", EXPENSE, "#123456")
    services.categories.create("Hoteles", EXPENSE, "#654321", parent_id=viajes.id)
    services.categories.create("Aéreos", EXPENSE, "#654321", parent_id=viajes.id)

    tree = services.categories.category_tree(EXPENSE)

    assert [node.category.name for node in tree][-3:] == ["Viajes", "Vivienda", "Otros"]
    viajes_node = next(node for node in tree if node.category.id == viajes.id)
    assert [child.name for child in viajes_node.children] == ["Aéreos", "Hoteles"]
    assert all(not node.category.is_subcategory for node in tree)


def test_transaction_count_includes_subcategories(services, pesos):
    viajes = services.categories.create("Viajes", EXPENSE, "#123456")
    hoteles = services.categories.create("Hoteles", EXPENSE, "#654321", parent_id=viajes.id)
    for category in (viajes, hoteles, hoteles):
        services.transactions.create(
            expense_draft(services, pesos.id, ars("10"), category_id=category.id)
        )

    assert services.categories.transaction_count(viajes.id) == 3
    assert services.categories.transaction_count(hoteles.id) == 2
