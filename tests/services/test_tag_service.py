"""Tags: created by name while recording movements, merged, deleted and added up."""

from datetime import date
from decimal import Decimal

import pytest
from factories import ars, expense_draft, income_draft, usd

from nodus.models.palette import PALETTE
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.errors import ValidationError


def tagged_expense(services, account, amount, *tags, on=date(2026, 11, 2)):
    return services.transactions.create(
        expense_draft(services, account.id, amount, on, tag_names=tags)
    )


def tag_names(services, transaction) -> list[str]:
    return [t.name for t in services.transactions.tags_for([transaction.id])[transaction.id]]


def test_saving_creates_tags_once_ignoring_case_and_accents(services, pesos):
    first = tagged_expense(services, pesos, ars("10"), "Vacaciones 2026", "Trabajo")
    second = tagged_expense(services, pesos, ars("20"), "vacaciónes 2026", "  ", "VACACIONES 2026")

    assert tag_names(services, first) == ["Trabajo", "Vacaciones 2026"]
    assert tag_names(services, second) == ["Vacaciones 2026"]
    assert [t.name for t in services.tags.list_tags()] == ["Trabajo", "Vacaciones 2026"]
    assert [t.color for t in services.tags.list_tags()] == [PALETTE[1], PALETTE[0]]


def test_editing_replaces_the_tags(services, pesos):
    expense = tagged_expense(services, pesos, ars("10"), "Viaje")

    services.transactions.update(
        expense.id, expense_draft(services, pesos.id, ars("10"), tag_names=("Mudanza",))
    )

    assert tag_names(services, services.transactions.get(expense.id)) == ["Mudanza"]


def test_matches_and_find(services, pesos):
    tagged_expense(services, pesos, ars("10"), "Vacaciones", "Casa de verano")

    assert [t.name for t in services.tags.matches("vaca")] == ["Vacaciones"]
    assert [t.name for t in services.tags.matches("ver")] == ["Casa de verano"]
    assert services.tags.find("VACACIONES").name == "Vacaciones"
    assert services.tags.matches("") == []


def test_names_are_unique(services):
    services.tags.create("Viaje")

    with pytest.raises(ValidationError, match="Ya existe"):
        services.tags.create("viaje")
    with pytest.raises(ValidationError, match="letras o números"):
        services.tags.create("¡!")


def test_rename_and_recolor(services):
    tag = services.tags.create("Viaje")

    services.tags.update(tag.id, "Viaje a Bariloche", "#123456")

    assert services.tags.get(tag.id).name == "Viaje a Bariloche"
    assert services.tags.get(tag.id).color == "#123456"


def test_merge_moves_the_movements(services, pesos):
    tagged_expense(services, pesos, ars("10"), "Viaje")
    both = tagged_expense(services, pesos, ars("20"), "Viaje", "Vacaciones")
    viaje, vacaciones = services.tags.find("Viaje"), services.tags.find("Vacaciones")

    services.tags.merge(viaje.id, vacaciones.id)

    assert services.tags.find("Viaje") is None
    assert services.tags.transaction_count(vacaciones.id) == 2
    assert tag_names(services, both) == ["Vacaciones"]
    with pytest.raises(ValidationError):
        services.tags.merge(vacaciones.id, vacaciones.id)


def test_delete_keeps_the_movements(services, pesos):
    expense = tagged_expense(services, pesos, ars("10"), "Viaje")

    assert services.tags.delete(services.tags.find("Viaje").id) == 1

    assert services.transactions.get(expense.id).amount == ars("10")
    assert services.transactions.tags_for([expense.id]) == {}


def test_merge_many_and_delete_many(services, pesos):
    both = tagged_expense(services, pesos, ars("10"), "Viaje", "Vacaciones")
    tagged_expense(services, pesos, ars("20"), "Paseo")
    work = tagged_expense(services, pesos, ars("30"), "Trabajo")
    viaje, vacaciones, paseo = (services.tags.find(n) for n in ["Viaje", "Vacaciones", "Paseo"])

    services.tags.merge_many([viaje.id, vacaciones.id, paseo.id], vacaciones.id)

    assert tag_names(services, both) == ["Vacaciones"]
    assert services.tags.transaction_count(vacaciones.id) == 2
    trabajo = services.tags.find("Trabajo")
    assert services.tags.delete_many([vacaciones.id, trabajo.id]) == 3
    assert services.tags.list_tags() == []
    assert services.transactions.get(work.id).amount == ars("30")


def test_summaries_add_up_in_pesos(services, pesos, dollars):
    services.exchange_rates.set_rate(date(2026, 11, 1), Decimal("1000"))
    tagged_expense(services, pesos, ars("5000"), "Viaje")
    tagged_expense(services, dollars, usd("10"), "Viaje")
    tagged_expense(services, dollars, usd("1"), "Viaje", on=date(2026, 10, 1))  # no rate yet
    services.transactions.create(
        income_draft(services, pesos.id, ars("1000"), date(2026, 11, 3), tag_names=("Viaje",))
    )
    services.tags.create("Sin uso")

    viaje, sin_uso = services.tags.summaries()

    assert (viaje.tag.name, viaje.count, viaje.net, viaje.unconverted) == (
        "Viaje", 4, ars("-14000"), 1,
    )  # fmt: skip
    assert (viaje.first_on, viaje.last_on) == (date(2026, 10, 1), date(2026, 11, 3))
    assert (sin_uso.count, sin_uso.net, sin_uso.first_on) == (0, ars("0"), None)
    assert services.tags.summary(viaje.tag.id) == viaje
    assert services.tags.summary(sin_uso.tag.id) == sin_uso


def test_filter_by_tag(services, pesos):
    tagged_expense(services, pesos, ars("10"), "Viaje")
    viaje = services.tags.find("Viaje")

    found = services.transactions.list_transactions(TransactionFilter(tag_id=viaje.id))

    assert len(found) == 1
