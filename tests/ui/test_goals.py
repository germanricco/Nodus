from datetime import date
from decimal import Decimal

import pytest
from factories import ars, data_since, expense_draft, income_draft, usd
from PySide6.QtCore import Qt

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.models.goal import Goal, GoalProgress, GoalShare, GoalState
from nodus.models.period import Month
from nodus.services.goal_service import GoalDraft
from nodus.services.notification_service import NoticeKind
from nodus.ui.dialogs.goal_dialog import GoalDialog
from nodus.ui.navigation import DetailId, PageId
from nodus.ui.pages import accounts_page, goals_page
from nodus.ui.pages.accounts_page import AccountsPage
from nodus.ui.pages.goal_detail_page import month_change_text
from nodus.ui.pages.goals_page import GoalsPage
from nodus.ui.widgets.goal_bar import goal_sentence, saved_of_target

TODAY = date(2026, 11, 13)


@pytest.fixture
def savings(services, database):
    """US$ 500 in a dollar savings account, with data since January."""
    account = services.accounts.create("Ahorro", AccountType.SAVINGS, Currency.USD, usd("500"))
    data_since(database, date(2026, 1, 10))
    return account


@pytest.fixture
def page(qtbot, services, event_bus, theme_manager) -> GoalsPage:
    goals = GoalsPage(services, event_bus, theme_manager)
    qtbot.addWidget(goals)
    goals.refresh(TODAY)
    return goals


def make_goal(services, account, percent=100, target="2000", on=date(2027, 3, 31), name="Viaje"):
    draft = GoalDraft(name, usd(target), on, (GoalShare(account.id, percent),))
    return services.goals.create(draft, TODAY)


def progress(state, eta=None, needed="295", remaining="1180"):
    return GoalProgress(
        state, usd("2000"), usd("820"), usd(remaining), usd(needed) if needed else None,
        usd("300"), eta, usd("20"),
    )  # fmt: skip


GOAL = Goal(1, "Viaje", usd("2000"), date(2027, 3, 31), (GoalShare(1, 100),))


class TestSentences:
    @pytest.mark.parametrize(
        ("state", "eta", "expected"),
        [
            (
                GoalState.ON_TRACK,
                Month(2027, 2),
                "Vas bien: a este ritmo llegas en febrero de 2027.",
            ),
            (
                GoalState.BEHIND,
                Month(2027, 8),
                "A este ritmo llegas en agosto de 2027, 5 meses tarde. "
                "Para llegar a tiempo hacen falta US$ 295,00 por mes.",
            ),
            (
                GoalState.BEHIND,
                None,
                "Tu ahorro no viene creciendo en los últimos meses. "
                "Para llegar a tiempo hacen falta US$ 295,00 por mes.",
            ),
            (
                GoalState.OVERDUE,
                None,
                "La fecha pasó y faltan US$ 1.180,00. Cambia la fecha o el objetivo.",
            ),
            (
                GoalState.NO_HISTORY,
                None,
                "Todavía no hay 3 meses para medir tu ritmo. "
                "Para llegar a tiempo hacen falta US$ 295,00 por mes.",
            ),
            (GoalState.REACHED, None, "Alcanzada."),
        ],
    )
    def test_each_state_says_where_it_stands(self, state, eta, expected):
        assert goal_sentence(GOAL, progress(state, eta)) == expected

    def test_without_a_date(self):
        sentence = goal_sentence(GOAL, progress(GoalState.NO_DATE, Month(2027, 6), needed=None))

        assert sentence == "A este ritmo llegas en junio de 2027."

    def test_reached_on_a_day(self):
        reached = Goal(1, "Viaje", usd("2000"), None, (), reached_on=date(2027, 3, 12))

        assert goal_sentence(reached, progress(GoalState.REACHED)) == "Alcanzada el 12/03/2027."

    def test_hidden_amounts_keep_the_percent(self):
        shown = progress(GoalState.OVERDUE)

        assert "••••" in goal_sentence(GOAL, shown, hidden=True)
        assert saved_of_target(shown, hidden=True) == "US$ •••• de US$ •••• · 41 %"


class TestPage:
    def test_empty_offers_to_add_one(self, page):
        assert page.rows == []
        assert page.create_button.text() == "Agregar meta"

    def test_goals_go_to_their_section(self, services, page, savings):
        archived = make_goal(services, savings, 100, name="Auto")
        services.goals.set_archived(archived.id, True)  # which frees the account
        make_goal(services, savings, 60)
        make_goal(services, savings, 40, target="100", name="Regalo")
        page.refresh(TODAY)

        assert page.section_titles == ["En curso", "Alcanzadas", "Archivadas"]
        assert [row.goal.name for row in page.rows] == ["Viaje", "Regalo", "Auto"]

    def test_a_row_says_how_far_it_got(self, services, page, savings):
        make_goal(services, savings)
        page.refresh(TODAY)

        [row] = page.rows
        assert row.figures_label.text() == "US$ 500,00 de US$ 2.000,00 · 25 %"
        assert row.pill.text() == "Atrasada"  # nothing saved since January

    def test_without_a_rate_it_offers_to_load_it(self, services, page, savings):
        pesos = services.accounts.create("Banco", AccountType.BANK, Currency.ARS, ars("1000"))
        services.goals.create(
            GoalDraft("Viaje", usd("2000"), None, (GoalShare(pesos.id, 100),)), TODAY
        )
        page.refresh(TODAY)

        [row] = page.rows
        assert row.pill.text() == "Sin cotización"
        assert row.rate_button.isVisibleTo(row)

    def test_grows_with_the_balance(self, services, event_bus, page, savings):
        make_goal(services, savings)
        services.transactions.create(income_draft(services, savings.id, usd("500"), on=TODAY))
        event_bus.transactions_changed.emit()

        assert page.rows[0].figures_label.text().startswith("US$ 1.000,00")

    def test_hidden_amounts(self, services, event_bus, page, savings):
        make_goal(services, savings)
        services.settings.set_amounts_hidden(True)
        event_bus.amounts_hidden_changed.emit(True)

        assert page.rows[0].figures_label.text() == "US$ •••• de US$ •••• · 25 %"

    def test_archive_and_delete(self, monkeypatch, services, page, savings):
        goal = make_goal(services, savings)
        page.refresh(TODAY)
        page.toggle_archived(page.rows[0].goal)
        assert services.goals.get(goal.id).is_archived

        texts = []
        monkeypatch.setattr(goals_page, "confirm", lambda _p, _t, text: texts.append(text) or True)
        page.delete_goal(services.goals.get(goal.id))

        assert services.goals.list_goals() == []
        assert "Las cuentas y sus movimientos no se tocan." in texts[0]
        assert services.accounts.balance(savings.id, TODAY) == usd("500")


class TestDialog:
    def dialog(self, qtbot, services, event_bus, **kwargs) -> GoalDialog:
        dialog = GoalDialog(services, event_bus, today=TODAY, **kwargs)
        qtbot.addWidget(dialog)
        return dialog

    def test_creates_a_goal(self, qtbot, services, event_bus, savings):
        dialog = self.dialog(qtbot, services, event_bus)
        dialog.name_input.setText("Viaje")
        dialog.currency_input.setCurrentIndex(dialog.currency_input.findData(Currency.USD))
        dialog.target_input.line_edit.setText("2.000")
        dialog.shares_input.row_for(savings.id).check.setChecked(True)

        with qtbot.waitSignal(event_bus.goals_changed):
            qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

        [goal] = services.goals.list_goals()
        assert (goal.name, goal.target, goal.target_date) == ("Viaje", usd("2000"), None)
        assert goal.shares == (GoalShare(savings.id, 100),)

    def test_says_what_each_account_adds_and_what_it_takes(
        self, qtbot, services, event_bus, savings
    ):
        dialog = self.dialog(qtbot, services, event_bus)
        dialog.currency_input.setCurrentIndex(dialog.currency_input.findData(Currency.USD))
        dialog.target_input.line_edit.setText("2500")
        dialog.dated_input.setChecked(True)
        dialog.date_input.set_day(date(2027, 3, 31))
        row = dialog.shares_input.row_for(savings.id)
        row.check.setChecked(True)
        row.percent_input.setText("50")

        assert row.hint.text() == "aporta US$ 250,00 hoy"
        assert dialog.summary_label.text() == (
            "Para llegar a US$ 2.500,00 en marzo de 2027 hacen falta unos US$ 562,50 por mes."
        )

    def test_says_how_much_of_an_account_is_free(self, qtbot, services, event_bus, savings):
        make_goal(services, savings, 60)

        dialog = self.dialog(qtbot, services, event_bus)

        row = dialog.shares_input.row_for(savings.id)
        assert row.hint.text() == "quedan 40 % libres"
        assert row.percent_input.text() == "40"

    def test_too_much_of_an_account_shows_under_the_accounts(
        self, qtbot, services, event_bus, savings
    ):
        make_goal(services, savings, 60)
        dialog = self.dialog(qtbot, services, event_bus)
        dialog.name_input.setText("Auto")
        dialog.target_input.line_edit.setText("100")
        row = dialog.shares_input.row_for(savings.id)
        row.check.setChecked(True)
        row.percent_input.setText("50")

        dialog._on_save()

        assert dialog.field_error(dialog.shares_input) == (
            "«Ahorro» ya tiene 60 % en «Viaje»: quedan 40 %."
        )

    def test_edits_keep_its_accounts(self, qtbot, services, event_bus, savings):
        goal = make_goal(services, savings, 60)

        dialog = self.dialog(qtbot, services, event_bus, goal=goal)
        dialog.target_input.line_edit.setText("3.000")
        dialog._on_save()

        updated = services.goals.get(goal.id)
        assert (updated.target, updated.shares) == (usd("3000"), (GoalShare(savings.id, 60),))
        assert updated.target_date == date(2027, 3, 31)

    def test_already_covered(self, qtbot, services, event_bus, savings):
        dialog = self.dialog(qtbot, services, event_bus, account=savings)
        dialog.currency_input.setCurrentIndex(dialog.currency_input.findData(Currency.USD))
        dialog.target_input.line_edit.setText("400")

        assert dialog.summary_label.text() == "Ya está cubierta: tus cuentas ya suman el objetivo."

    def test_other_currencies_need_a_rate(self, qtbot, services, event_bus, savings):
        dialog = self.dialog(qtbot, services, event_bus, account=savings)
        dialog.currency_input.setCurrentIndex(dialog.currency_input.findData(Currency.ARS))
        dialog.target_input.line_edit.setText("1.000.000")
        assert "cotización" in dialog.summary_label.text()

        services.exchange_rates.set_rate(TODAY, Decimal("1000"))
        dialog.target_input.line_edit.setText("2.000.000")

        assert dialog.shares_input.row_for(savings.id).hint.text() == "aporta $ 500.000,00 hoy"


class TestFromAnAccount:
    def test_savings_accounts_offer_a_goal(
        self, qtbot, services, event_bus, theme_manager, savings
    ):
        services.accounts.create("Banco", AccountType.BANK, Currency.ARS, ars("0"))
        page = AccountsPage(services, event_bus, theme_manager)
        qtbot.addWidget(page)
        page.refresh()

        offers = {
            row.account.name: "Usar en una meta…" in [a.text for a in row.actions()]
            for row in page.findChildren(accounts_page.AccountRow)
        }

        assert offers == {"Ahorro": True, "Banco": False}

    def test_opens_the_form_with_the_account_ticked(
        self, monkeypatch, qtbot, services, event_bus, theme_manager, savings
    ):
        opened = []
        monkeypatch.setattr(GoalDialog, "exec", lambda dialog: opened.append(dialog))
        page = AccountsPage(services, event_bus, theme_manager)
        qtbot.addWidget(page)
        page.refresh()
        [row] = page.findChildren(accounts_page.AccountRow)

        next(a for a in row.actions() if a.text == "Usar en una meta…").callback()

        assert opened[0].shares_input.shares() == (GoalShare(savings.id, 100),)


def test_spending_lowers_it(services, savings):
    goal = make_goal(services, savings)
    services.transactions.create(expense_draft(services, savings.id, usd("100"), on=TODAY))

    assert services.goals.progress(goal, TODAY).saved == usd("400")


def notice_kinds(services, day) -> list[NoticeKind]:
    return [n.kind for n in services.notifications.notices(day, None)]


class TestDetail:
    @pytest.fixture
    def detail(self, window, services, savings):
        goal = make_goal(services, savings, 60, on=date(2030, 12, 31))
        page = window.detail(DetailId.GOAL)
        window.show_detail(DetailId.GOAL, goal.id)
        return page

    def test_a_click_on_the_row_opens_it(self, qtbot, window, services, savings):
        goal = make_goal(services, savings)
        window.show_page(PageId.GOALS)
        [row] = window.page(PageId.GOALS).rows

        qtbot.mouseClick(row, Qt.MouseButton.LeftButton)

        detail = window.detail(DetailId.GOAL)
        assert window.current_page is detail
        assert detail.title_label.text() == "Viaje"
        assert detail.goal.id == goal.id
        assert window.sidebar.nav_button(PageId.GOALS).isChecked()

    def test_figures_and_accounts(self, detail):
        assert detail.saved_label.text() == "US$ 300,00"
        assert detail.remaining_label.text() == "US$ 1.700,00"
        assert detail.target_note.text() == "para diciembre de 2030"
        [row] = detail.account_rows
        assert row.counted_label.text() == "US$ 300,00"

    def test_the_chart_marks_the_target(self, detail):
        assert detail.chart._reference == usd("2000").cents
        assert detail.chart.points()[-1].value == usd("300").cents

    def test_an_account_opens_its_page(self, window, detail, savings):
        detail.account_rows[0].clicked.emit()

        assert window.current_page is window.detail(DetailId.ACCOUNT)
        assert window.detail(DetailId.ACCOUNT).account.id == savings.id

    def test_deleting_goes_back_to_the_list(self, monkeypatch, window, services, detail):
        monkeypatch.setattr(goals_page, "confirm", lambda *_args: True)

        detail.delete()

        assert services.goals.list_goals() == []
        assert window.current_page is window.page(PageId.GOALS)

    @pytest.mark.parametrize(
        ("change", "text"),
        [
            (usd("50"), "Este mes subió US$ 50,00"),
            (usd("-150"), "Este mes bajó US$ 150,00"),
            (usd("0"), "Este mes, sin cambios"),
        ],
    )
    def test_this_months_change(self, change, text):
        assert month_change_text(change, hidden=False) == text


class TestAccountGoals:
    def test_an_account_names_the_goals_it_fills(self, window, services, savings):
        goal = make_goal(services, savings, 60)
        account_page = window.detail(DetailId.ACCOUNT)
        window.show_detail(DetailId.ACCOUNT, savings.id)

        assert account_page.goals_line.isVisible()
        [link] = [
            b for b in account_page.goals_line.findChildren(goals_page.QPushButton) if b.isVisible()
        ]
        assert link.text() == "Viaje (60 %)"
        link.click()
        assert window.current_page is window.detail(DetailId.GOAL)
        assert window.detail(DetailId.GOAL).goal.id == goal.id

    def test_not_when_it_fills_none(self, window, savings):
        window.show_detail(DetailId.ACCOUNT, savings.id)

        assert not window.detail(DetailId.ACCOUNT).goals_line.isVisible()


class TestReachedNotice:
    def test_announced_once_until_seen(self, services, savings):
        today = date.today()
        goal = services.goals.create(
            GoalDraft("Viaje", usd("400"), None, (GoalShare(savings.id, 100),)), today
        )

        assert NoticeKind.GOAL_REACHED in notice_kinds(services, today)
        [notice] = [
            n
            for n in services.notifications.notices(today, None)
            if n.kind is NoticeKind.GOAL_REACHED
        ]
        assert notice.title == "Alcanzaste «Viaje»"
        services.goals.mark_seen(goal.id)
        assert NoticeKind.GOAL_REACHED not in notice_kinds(services, today)

    def test_ver_meta_opens_it_and_clears_the_bell(self, window, services, event_bus, savings):
        goal = services.goals.create(
            GoalDraft("Viaje", usd("400"), None, (GoalShare(savings.id, 100),)), date.today()
        )
        event_bus.goals_changed.emit()
        window.open_notifications()
        [row] = [
            r for r in window.notification_panel.rows if r.notice.kind is NoticeKind.GOAL_REACHED
        ]
        assert (row.action_button.text(), row.dismiss_button.text()) == ("Ver meta", "Listo")

        row.action_button.click()

        assert window.current_page is window.detail(DetailId.GOAL)
        assert services.goals.get(goal.id).reached_seen
        assert services.goals.get(goal.id).reached_on == date.today()
