from datetime import date
from decimal import Decimal

import pytest
from factories import ars, usd

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.services.errors import NotFoundError, ValidationError

TODAY = date(2026, 11, 13)


@pytest.fixture
def groups(services):
    return services.account_groups


def names(groups) -> list[str]:
    return [g.name for g in groups.list_groups()]


def add_account(services, name, currency=Currency.ARS, amount="1000"):
    money = ars(amount) if currency is Currency.ARS else usd(amount)
    return services.accounts.create(name, AccountType.BANK, currency, money)


class TestNames:
    def test_new_groups_go_last(self, groups):
        groups.create("Bancos")
        groups.create("  Billeteras ")

        assert names(groups) == ["Bancos", "Billeteras"]

    def test_names_are_unique_ignoring_case_and_accents(self, groups):
        groups.create("Inversión")

        with pytest.raises(ValidationError, match="Ya existe el grupo «Inversión»"):
            groups.create("inversion")

    def test_rename_keeps_its_own_name_free(self, groups):
        bancos = groups.create("Bancos")
        groups.create("Efectivo")

        groups.rename(bancos.id, "BANCOS")
        assert names(groups) == ["BANCOS", "Efectivo"]
        with pytest.raises(ValidationError):
            groups.rename(bancos.id, "efectivo")

    def test_empty_name_is_rejected(self, groups):
        with pytest.raises(ValidationError):
            groups.create("   ")


class TestOrder:
    def test_reorder(self, groups):
        a, b, c = (groups.create(n) for n in ("A", "B", "C"))

        groups.reorder([c.id, a.id, b.id])

        assert names(groups) == ["C", "A", "B"]

    def test_reorder_must_name_every_group_once(self, groups):
        a = groups.create("A")
        groups.create("B")

        with pytest.raises(ValidationError):
            groups.reorder([a.id])
        with pytest.raises(ValidationError):
            groups.reorder([a.id, a.id])
        assert names(groups) == ["A", "B"]


class TestAccounts:
    def test_a_moved_account_goes_last_in_its_group(self, services, groups):
        bancos = groups.create("Bancos")
        galicia, nacion = add_account(services, "Galicia"), add_account(services, "Nación")
        groups.move_account(nacion.id, bancos.id)
        groups.move_account(galicia.id, bancos.id)

        sections = groups.sections(services.accounts.list_accounts())

        assert [(s.group.name, [a.name for a in s.accounts]) for s in sections] == [
            ("Bancos", ["Nación", "Galicia"])
        ]

    def test_accounts_in_no_group_come_last(self, services, groups):
        bancos = groups.create("Bancos")
        groups.create("Inversiones")
        efectivo, banco = add_account(services, "Efectivo"), add_account(services, "Banco")
        groups.move_account(banco.id, bancos.id)

        sections = groups.sections(services.accounts.list_accounts())

        assert [(s.group and s.group.name, [a.name for a in s.accounts]) for s in sections] == [
            ("Bancos", ["Banco"]),
            ("Inversiones", []),
            (None, ["Efectivo"]),
        ]
        assert efectivo.group_id is None

    def test_moving_out_of_a_group(self, services, groups):
        bancos = groups.create("Bancos")
        banco = add_account(services, "Banco")
        groups.move_account(banco.id, bancos.id)

        groups.move_account(banco.id, None)

        assert services.accounts.get(banco.id).group_id is None

    def test_moving_to_a_missing_group_fails(self, services, groups):
        banco = add_account(services, "Banco")

        with pytest.raises(NotFoundError):
            groups.move_account(banco.id, 99)

    def test_editing_an_account_keeps_its_group(self, services, groups):
        bancos = groups.create("Bancos")
        banco = add_account(services, "Banco")
        groups.move_account(banco.id, bancos.id)

        services.accounts.update(banco.id, "Banco Nación", AccountType.BANK, ars("5"))
        services.accounts.set_archived(banco.id, True)

        assert services.accounts.get(banco.id).group_id == bancos.id

    def test_deleting_a_group_keeps_its_accounts(self, services, groups):
        bancos = groups.create("Bancos")
        banco = add_account(services, "Banco")
        groups.move_account(banco.id, bancos.id)
        assert groups.account_count(bancos.id) == 1

        groups.delete(bancos.id)

        assert names(groups) == []
        account = services.accounts.get(banco.id)
        assert (account.name, account.group_id) == ("Banco", None)
        assert services.accounts.balance(banco.id) == ars("1000")


class TestTotal:
    def test_one_currency_adds_up_exactly(self, services, groups):
        accounts = [
            add_account(services, "A", amount="1000"),
            add_account(services, "B", amount="250"),
        ]

        total = groups.total(accounts, services.accounts.balances(TODAY), TODAY)

        assert (total.amount, total.approximate) == (ars("1250"), False)

    def test_dollars_alone_stay_in_dollars(self, services, groups):
        accounts = [add_account(services, "Ahorro", Currency.USD, "300")]

        total = groups.total(accounts, services.accounts.balances(TODAY), TODAY)

        assert (total.amount, total.approximate) == (usd("300"), False)

    def test_mixed_currencies_go_to_the_net_worths_and_are_approximate(self, services, groups):
        services.exchange_rates.set_rate(TODAY, Decimal("1000"))
        accounts = [
            add_account(services, "Banco", amount="5000"),
            add_account(services, "Ahorro", Currency.USD, "2"),
        ]
        balances = services.accounts.balances(TODAY)

        assert groups.total(accounts, balances, TODAY).amount == ars("7000")
        services.settings.set_net_worth_currency(Currency.USD)
        total = groups.total(accounts, balances, TODAY)
        assert (total.amount, total.approximate) == (usd("7"), True)

    def test_mixed_currencies_without_a_rate_have_no_total(self, services, groups):
        accounts = [add_account(services, "Banco"), add_account(services, "Ahorro", Currency.USD)]

        total = groups.total(accounts, services.accounts.balances(TODAY), TODAY)

        assert (total.amount, total.approximate) == (None, True)

    def test_an_empty_group_adds_up_to_zero(self, services, groups):
        assert groups.total([], {}, TODAY).amount == ars("0")


class TestPlace:
    """An account dragged to a group lands where it was dropped, and can be undone."""

    def order(self, services) -> list[list[str]]:
        sections = services.account_groups.sections(services.accounts.list_accounts())
        return [[a.name for a in s.accounts] for s in sections]

    @pytest.fixture
    def two_groups(self, services, groups):
        bancos = groups.create("Bancos")
        efectivo = groups.create("Efectivo")
        for name in ("Galicia", "Nación", "Santander"):
            groups.move_account(add_account(services, name).id, bancos.id)
        groups.move_account(add_account(services, "Billetera").id, efectivo.id)
        add_account(services, "Suelta")
        return bancos, efectivo

    def account(self, services, name):
        return next(a for a in services.accounts.list_accounts() if a.name == name)

    @pytest.mark.parametrize(
        ("gap", "expected"),
        [
            (0, ["Galicia", "Billetera"]),
            (1, ["Billetera", "Galicia"]),
            (9, ["Billetera", "Galicia"]),
        ],
    )
    def test_it_lands_at_its_gap(self, services, groups, two_groups, gap, expected):
        _, efectivo = two_groups

        groups.place_account(self.account(services, "Galicia").id, efectivo.id, gap)

        assert self.order(services) == [["Nación", "Santander"], expected, ["Suelta"]]

    def test_into_an_empty_group_and_out_of_every_group(self, services, groups, two_groups):
        vacio = groups.create("Vacío")

        groups.place_account(self.account(services, "Nación").id, vacio.id, 0)
        groups.place_account(self.account(services, "Billetera").id, None, 0)

        assert self.order(services) == [
            ["Galicia", "Santander"],
            [],
            ["Nación"],
            ["Billetera", "Suelta"],
        ]

    def test_it_is_undone_with_the_order_it_had(self, services, groups, two_groups):
        _, efectivo = two_groups
        before = self.order(services)

        groups.place_account(self.account(services, "Nación").id, efectivo.id, 0)
        assert services.undo.last.description == "Nación ahora está en Efectivo."
        services.undo.undo()

        assert self.order(services) == before

    def test_it_is_not_undone_over_a_later_move(self, services, groups, two_groups):
        _, efectivo = two_groups
        nacion = self.account(services, "Nación")
        groups.place_account(nacion.id, efectivo.id, 0)
        record = services.undo.last

        groups.move_account(nacion.id, None)

        with pytest.raises(ValidationError, match="ya no se puede deshacer"):
            services.undo.undo(record)
        assert services.accounts.get(nacion.id).group_id is None

    def test_out_of_a_group_says_so(self, services, groups, two_groups):
        groups.place_account(self.account(services, "Galicia").id, None, 0)

        assert services.undo.last.description == "Galicia quedó sin grupo."
