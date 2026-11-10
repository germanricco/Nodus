from datetime import date, timedelta
from decimal import Decimal

import pytest
from factories import TODAY, ars, category_id, eur, expense_draft, income_draft, usd

from nodus.models.installment_plan import InstallmentPlan
from nodus.models.transaction import TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.errors import NotFoundError, ValidationError
from nodus.services.payee_service import PayeeService

EXPENSE, INCOME = TransactionType.EXPENSE, TransactionType.INCOME


def payee_names(services) -> list[str]:
    return [p.name for p in services.payees.list_payees()]


def listed(services, **criteria):
    return services.transactions.list_transactions(TransactionFilter(**criteria))


@pytest.fixture
def groceries(services) -> int:
    return category_id(services, "Supermercado y comida", TransactionType.EXPENSE)


@pytest.fixture
def services_category(services) -> int:
    return category_id(services, "Servicios", TransactionType.EXPENSE)


class TestNames:
    def test_create_trims_and_lists_alphabetically(self, services):
        services.payees.create("  Verdulería ")
        services.payees.create("Ángel")
        services.payees.create("Coto")

        assert payee_names(services) == ["Ángel", "Coto", "Verdulería"]

    def test_duplicate_ignores_case_accents_and_signs(self, services):
        services.payees.create("Café Martínez")

        with pytest.raises(ValidationError, match="Ya existe «Café Martínez»"):
            services.payees.create("cafe-martinez")

    def test_renaming_onto_another_suggests_merging(self, services):
        services.payees.create("Coto")
        dia = services.payees.create("Día")

        with pytest.raises(ValidationError, match="Unir con"):
            services.payees.update(dia.id, "COTO", None)

    def test_renaming_keeps_its_own_name_free(self, services, groceries):
        coto = services.payees.create("coto")

        services.payees.update(coto.id, "Coto", groceries)

        assert services.payees.get(coto.id).default_category_id == groceries

    @pytest.mark.parametrize("name", ["", "   ", "¿?"])
    def test_name_needs_letters_or_digits(self, services, name):
        with pytest.raises(ValidationError):
            services.payees.create(name)

    def test_default_category_must_exist(self, services):
        with pytest.raises(NotFoundError):
            services.payees.create("Coto", default_category_id=999)

    def test_matches_puts_prefixes_first(self, services):
        for name in ["Supermercado Día", "Día", "Diarios", "Coto"]:
            services.payees.create(name)

        assert [p.name for p in services.payees.matches("dia")] == [
            "Día", "Diarios", "Supermercado Día",
        ]  # fmt: skip
        assert services.payees.matches("  ") == []

    def test_find_ignores_case_and_accents(self, services):
        verduleria = services.payees.create("Verdulería")

        assert services.payees.find("VERDULERIA") == verduleria
        assert services.payees.find("Otra") is None


class TestTransactions:
    def test_new_name_creates_the_payee(self, services, pesos):
        created = services.transactions.create(
            expense_draft(services, pesos.id, ars("10"), payee_name=" Verdulería ")
        )

        payee = services.payees.find("verduleria")
        assert payee.name == "Verdulería"
        assert services.transactions.get(created.id).payee_id == payee.id

    def test_existing_name_reuses_the_payee(self, services, pesos):
        coto = services.payees.create("Coto")

        created = services.transactions.create(
            expense_draft(services, pesos.id, ars("10"), payee_name="coto")
        )

        assert services.transactions.get(created.id).payee_id == coto.id
        assert payee_names(services) == ["Coto"]

    def test_empty_name_leaves_no_payee(self, services, pesos):
        created = services.transactions.create(
            expense_draft(services, pesos.id, ars("10"), payee_name="Coto")
        )

        services.transactions.update(created.id, expense_draft(services, pesos.id, ars("10")))

        assert services.transactions.get(created.id).payee_id is None

    def test_invalid_transaction_leaves_no_orphan_payee(self, services, pesos):
        with pytest.raises(ValidationError):
            services.transactions.create(
                expense_draft(services, pesos.id, ars("0"), payee_name="Fantasma")
            )

        assert payee_names(services) == []

    def test_filter_by_payee(self, services, pesos):
        services.transactions.create(
            expense_draft(services, pesos.id, ars("10"), payee_name="Coto")
        )
        services.transactions.create(expense_draft(services, pesos.id, ars("20"), payee_name="Día"))

        (found,) = listed(services, payee_id=services.payees.find("Día").id)
        assert found.amount == ars("20")

    def test_text_search_matches_payee_name_without_accents(self, services, pesos):
        services.transactions.create(
            expense_draft(services, pesos.id, ars("10"), payee_name="Verdulería")
        )
        services.transactions.create(expense_draft(services, pesos.id, ars("20"), note="verduras"))
        services.transactions.create(expense_draft(services, pesos.id, ars("30"), note="otra"))

        assert sorted(t.amount.cents for t in listed(services, text="verdu")) == [1000, 2000]
        assert [t.amount for t in listed(services, text="VERDULERIA")] == [ars("10")]


class TestDeleteAndMerge:
    def test_delete_returns_count_and_keeps_transactions(self, services, pesos):
        for amount in ["10", "20"]:
            services.transactions.create(
                expense_draft(services, pesos.id, ars(amount), payee_name="Coto")
            )
        coto = services.payees.find("Coto")

        assert services.payees.transaction_count(coto.id) == 2
        assert services.payees.delete(coto.id) == 2

        assert payee_names(services) == []
        assert [t.payee_id for t in listed(services)] == [None, None]

    def test_merge_moves_transactions_and_inherits_default_category(
        self, services, pesos, groceries
    ):
        services.transactions.create(
            expense_draft(services, pesos.id, ars("10"), payee_name="Coto Online")
        )
        source = services.payees.find("Coto Online")
        services.payees.update(source.id, source.name, groceries)
        target = services.payees.create("Coto")

        services.payees.merge(source.id, target.id)

        assert payee_names(services) == ["Coto"]
        assert services.payees.get(target.id).default_category_id == groceries
        assert [t.payee_id for t in listed(services)] == [target.id]

    def test_merge_keeps_the_target_default(self, services, groceries, services_category):
        source = services.payees.create("A", groceries)
        target = services.payees.create("B", services_category)

        services.payees.merge(source.id, target.id)

        assert services.payees.get(target.id).default_category_id == services_category

    def test_delete_many(self, services, pesos):
        for name in ["Coto", "Día", "Jumbo"]:
            services.transactions.create(
                expense_draft(services, pesos.id, ars("10"), payee_name=name)
            )
        ids = [services.payees.find(name).id for name in ["Coto", "Día"]]

        assert services.payees.delete_many(ids) == 2

        assert payee_names(services) == ["Jumbo"]

    def test_merge_many_into_one(self, services, pesos, groceries):
        for name in ["Coto", "Coto Online", "COTO Digital"]:
            services.transactions.create(
                expense_draft(services, pesos.id, ars("10"), payee_name=name)
            )
        coto, online, digital = (
            services.payees.find(n) for n in ["Coto", "Coto Online", "COTO Digital"]
        )
        services.payees.update(digital.id, digital.name, groceries)

        # The target may come among the sources, as when merging a whole selection.
        services.payees.merge_many([coto.id, online.id, digital.id], coto.id)

        assert payee_names(services) == ["Coto"]
        assert services.payees.get(coto.id).default_category_id == groceries
        assert [t.payee_id for t in listed(services)] == [coto.id] * 3

    def test_cannot_merge_into_itself(self, services):
        coto = services.payees.create("Coto")

        with pytest.raises(ValidationError):
            services.payees.merge(coto.id, coto.id)

    def test_deleting_the_default_category_clears_it(self, services):
        category = services.categories.create("Mascotas", TransactionType.EXPENSE, "#888888")
        payee = services.payees.create("Veterinaria", category.id)

        services.categories.delete(category.id)

        assert services.payees.get(payee.id).default_category_id is None


class TestSuggestedCategory:
    def test_default_category_of_the_same_kind(self, services, groceries):
        coto = services.payees.create("Coto", groceries)

        assert services.payees.suggested_category(coto.id, TransactionType.EXPENSE) == groceries

    def test_falls_back_to_latest_of_that_kind(self, services, pesos, groceries, services_category):
        services.transactions.create(
            expense_draft(services, pesos.id, ars("10"), date(2026, 11, 1), payee_name="Empresa")
        )
        services.transactions.create(
            expense_draft(
                services, pesos.id, ars("10"), date(2026, 11, 2),
                payee_name="Empresa", category_id=services_category,
            )
        )  # fmt: skip
        services.transactions.create(
            income_draft(services, pesos.id, ars("99"), payee_name="Empresa")
        )
        empresa = services.payees.find("Empresa")
        sueldo = category_id(services, "Sueldo", TransactionType.INCOME)
        services.payees.update(empresa.id, empresa.name, sueldo)

        suggested = services.payees.suggested_category(empresa.id, TransactionType.EXPENSE)

        assert suggested == services_category
        assert services.payees.suggested_category(empresa.id, TransactionType.INCOME) == sueldo

    def test_none_without_default_or_history(self, services):
        coto = services.payees.create("Coto")

        assert services.payees.suggested_category(coto.id, TransactionType.EXPENSE) is None


class TestSummaries:
    def test_totals_converted_and_most_used_first(
        self, services, pesos, dollars, euros, groceries, services_category
    ):
        services.exchange_rates.set_rate(date(2026, 11, 3), Decimal("1000"))
        services.payees.create("Sin uso")
        services.transactions.create(
            expense_draft(services, pesos.id, ars("500"), date(2026, 11, 4), payee_name="Coto")
        )
        services.transactions.create(
            expense_draft(services, dollars.id, usd("2"), date(2026, 11, 4), payee_name="Coto")
        )
        services.transactions.create(
            expense_draft(
                services, euros.id, eur("1"), date(2026, 11, 1),
                payee_name="Coto", category_id=services_category,
            )
        )  # fmt: skip
        services.transactions.create(
            income_draft(services, pesos.id, ars("100"), date(2026, 11, 2), payee_name="Coto")
        )

        coto, unused = services.payees.summaries()

        assert coto.payee.name == "Coto"
        assert coto.count == 4
        assert coto.net == ars("-2400")
        assert coto.unconverted == 1
        assert coto.top_category.id == groceries
        assert (coto.first_on, coto.last_on) == (date(2026, 11, 1), date(2026, 11, 4))
        assert (unused.count, unused.net, unused.top_category, unused.first_on) == (
            0, ars("0"), None, None,
        )  # fmt: skip
        assert services.payees.summary(coto.payee.id) == coto
        assert services.payees.summary(unused.payee.id) == unused

    def test_summary_of_a_missing_payee(self, services):
        with pytest.raises(NotFoundError):
            services.payees.summary(999)


class TestSuggestionsByUse:
    """The payees used most come first, so a usual purchase takes a couple of clicks."""

    @staticmethod
    def spend(services, account, payee, days_ago=0, times=1, **overrides):
        for _ in range(times):
            services.transactions.create(
                expense_draft(
                    services, account.id, ars("100"), TODAY - timedelta(days=days_ago),
                    payee_name=payee, **overrides,
                )
            )  # fmt: skip

    def names(self, payees):
        return [p.name for p in payees]

    def test_the_most_used_and_latest_come_first(self, services, pesos):
        services.payees.create("Cabify")  # never used: alphabetical, at the end
        self.spend(services, pesos, "Carrefour", days_ago=1)
        self.spend(services, pesos, "Coto", days_ago=30, times=2)
        self.spend(services, pesos, "Chango", days_ago=200)

        found = services.payees.matches("c", EXPENSE, today=TODAY)

        assert self.names(found) == ["Coto", "Carrefour", "Chango", "Cabify"]

    def test_names_starting_with_the_text_still_come_first(self, services, pesos):
        self.spend(services, pesos, "Supermercado Día", times=3)
        services.payees.create("Día")

        found = services.payees.matches("dia", EXPENSE, today=TODAY)

        assert self.names(found) == ["Día", "Supermercado Día"]

    def test_the_chosen_category_comes_first(self, services, pesos):
        leisure = category_id(services, "Ocio", EXPENSE)
        self.spend(services, pesos, "Coto", times=3)
        self.spend(services, pesos, "Cine", category_id=leisure)

        assert self.names(services.payees.matches("c", EXPENSE, leisure, TODAY)) == [
            "Cine", "Coto",
        ]  # fmt: skip
        assert self.names(services.payees.frequent(EXPENSE, leisure, TODAY)) == ["Cine", "Coto"]

    def test_a_purchase_in_installments_counts_once(self, services, pesos):
        services.installments.create(
            expense_draft(
                services, pesos.id, ars("1200"), TODAY - timedelta(days=330),
                payee_name="Frávega",
            ),
            InstallmentPlan(None, 12, ars("1200"), TODAY - timedelta(days=330)),
        )  # fmt: skip
        self.spend(services, pesos, "Farmacia", times=2)

        assert self.names(services.payees.matches("f", EXPENSE, today=TODAY)) == [
            "Farmacia", "Frávega",
        ]  # fmt: skip

    def test_incomes_do_not_order_an_expense(self, services, pesos):
        for _ in range(3):
            services.transactions.create(
                income_draft(services, pesos.id, ars("100"), TODAY, payee_name="Acme")
            )
        self.spend(services, pesos, "Almacén")

        assert self.names(services.payees.matches("a", EXPENSE, today=TODAY)) == [
            "Almacén", "Acme",
        ]  # fmt: skip
        assert self.names(services.payees.frequent(INCOME, today=TODAY)) == ["Acme"]

    def test_frequent_shows_only_recent_use_and_a_few(self, services, pesos):
        services.payees.create("Nunca")
        self.spend(services, pesos, "Antes", days_ago=PayeeService.FREQUENT_DAYS + 1)
        for number in range(PayeeService.FREQUENT_COUNT + 1):
            self.spend(services, pesos, f"Tienda {number}", days_ago=number)

        found = self.names(services.payees.frequent(EXPENSE, today=TODAY))

        assert found == [f"Tienda {n}" for n in range(PayeeService.FREQUENT_COUNT)]

    def test_nothing_used_suggests_nothing_before_typing(self, services):
        services.payees.create("Coto")

        assert services.payees.frequent(EXPENSE, today=TODAY) == []
