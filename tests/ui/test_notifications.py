import dataclasses
from datetime import date, timedelta
from decimal import Decimal

import pytest
from factories import ars, category_id, charge_draft, data_since, expense_draft, manifest_answer
from menus import main_action, run_action, texts
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from nodus.models.period import Month
from nodus.models.transaction import TransactionType
from nodus.services.app.notification_service import NoticeKind
from nodus.services.external import update_service
from nodus.services.external.update_service import UpdateService
from nodus.ui import browser
from nodus.ui.dialogs import external_backup
from nodus.ui.navigation import PageId
from nodus.ui.shell.main_window import MainWindow
from nodus.ui.shell.notices import NOTICES

NEWER = manifest_answer("9.0.0")


@pytest.fixture
def requests() -> list[str]:
    return []


@pytest.fixture
def offline_window(qtbot, services, event_bus, theme_manager, requests) -> MainWindow:
    """A window whose update check gets a newer release without touching the network."""

    def fetch(url):
        requests.append(url)
        return NEWER

    with_fake_updates = dataclasses.replace(services, updates=UpdateService("0.2.0", fetch))
    window = MainWindow(with_fake_updates, event_bus, theme_manager)
    qtbot.addWidget(window)
    window.show()
    return window


def count(window) -> str:
    label = window.top_bar.notification_count
    return label.text() if label.isVisible() else ""


def open_row(row) -> None:
    """A click on the notice, away from its texts."""
    QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=QPoint(2, row.height() // 2))


def found_release(qtbot, window) -> None:
    window.check_for_updates()
    qtbot.waitUntil(lambda: count(window) == "1")


def test_starts_without_notifications_or_requests(offline_window, requests):
    assert count(offline_window) == ""
    assert requests == []


def test_newer_release_is_counted_and_listed(qtbot, offline_window):
    found_release(qtbot, offline_window)

    offline_window.top_bar.notifications_button.click()

    panel = offline_window.notification_panel
    assert panel.isVisible()
    assert [n.kind for n in offline_window.notices()] == [NoticeKind.UPDATE]
    assert "9.0.0" in offline_window.notices()[0].title
    assert main_action(panel.rows[0].actions()) == "Actualizar"
    assert panel.rows[0].toolTip() == "Actualizar"


def test_update_from_the_source_code_opens_the_release_page(qtbot, offline_window, monkeypatch):
    opened = []
    monkeypatch.setattr(
        browser.QDesktopServices, "openUrl", lambda url: opened.append(url.toString())
    )
    found_release(qtbot, offline_window)
    offline_window.open_notifications()

    open_row(offline_window.notification_panel.rows[0])

    assert opened == ["https://github.com/germanricco/Nodus/releases/tag/v9.0.0"]
    assert not offline_window.notification_panel.isVisible()


def test_dismissed_release_is_not_announced_again(qtbot, services, offline_window):
    found_release(qtbot, offline_window)
    offline_window.open_notifications()

    run_action(offline_window.notification_panel.rows[0].actions(), "Descartar esta versión")

    assert count(offline_window) == ""
    assert services.settings.dismissed_version() == "9.0.0"


def test_no_check_when_turned_off(services, offline_window, requests):
    services.settings.set_check_updates(False)

    offline_window.check_for_updates()

    assert requests == []
    assert count(offline_window) == ""


def window_with_answers(qtbot, services, event_bus, theme_manager, answers) -> MainWindow:
    """A window whose update checks get ``answers`` in turn: bytes, or an error to raise.
    Once they run out, every check gets the last one."""

    def fetch(_url):
        answer = answers.pop(0) if len(answers) > 1 else answers[0]
        if isinstance(answer, Exception):
            raise answer
        return answer

    with_fake_updates = dataclasses.replace(services, updates=UpdateService("0.2.0", fetch))
    window = MainWindow(with_fake_updates, event_bus, theme_manager)
    qtbot.addWidget(window)
    window.show()
    return window


def test_a_failed_check_tries_again_on_its_own(
    qtbot, services, event_bus, theme_manager, monkeypatch
):
    """As when GitHub limits a connection shared by many: the first check fails, and
    the next, without reopening Nodus, finds the new version."""
    monkeypatch.setattr(update_service, "RETRY_AFTER_FAILURE", timedelta(0))
    limited = OSError("HTTP Error 403: rate limit exceeded")
    window = window_with_answers(qtbot, services, event_bus, theme_manager, [limited, NEWER])

    window.check_for_updates()

    qtbot.waitUntil(lambda: count(window) == "1")


def test_a_failed_check_keeps_the_version_already_found(
    qtbot, services, event_bus, theme_manager, monkeypatch
):
    monkeypatch.setattr(update_service, "CHECK_EVERY", timedelta(0))
    checks = []
    offline = OSError("sin conexión")
    window = window_with_answers(qtbot, services, event_bus, theme_manager, [NEWER, offline])
    real_show = window._show_release
    monkeypatch.setattr(window, "_show_release", lambda c: (checks.append(c), real_show(c)))

    window.check_for_updates()
    qtbot.waitUntil(lambda: any(check.failed for check in checks))

    assert count(window) == "1"
    assert window.notices()[0].kind is NoticeKind.UPDATE


def test_turning_the_check_off_stops_the_next_ones(
    qtbot, services, event_bus, theme_manager, monkeypatch
):
    monkeypatch.setattr(update_service, "RETRY_AFTER_FAILURE", timedelta(0))
    window = window_with_answers(
        qtbot, services, event_bus, theme_manager, [OSError("sin conexión"), NEWER]
    )
    window.check_for_updates()
    services.settings.set_check_updates(False)

    qtbot.wait(200)

    assert count(window) == ""


def test_stale_rate_notice_leads_to_settings(qtbot, services, event_bus, offline_window, dollars):
    services.exchange_rates.set_rate(date.today() - timedelta(days=10), Decimal("1000"))
    event_bus.exchange_rates_changed.emit()
    assert count(offline_window) == "1"
    offline_window.open_notifications()

    open_row(offline_window.notification_panel.rows[0])

    assert offline_window.current_page is offline_window.page(PageId.SETTINGS)


def test_empty_panel_says_so(qtbot, offline_window):
    offline_window.open_notifications()

    assert offline_window.notification_panel.rows == []


def test_sidebar_foot_opens_settings(offline_window):
    offline_window.sidebar.nav_button(PageId.SETTINGS).click()

    assert offline_window.current_page is offline_window.page(PageId.SETTINGS)


def test_charges_notice_follows_payments_and_leads_to_the_charges(
    qtbot, services, event_bus, offline_window, pesos
):
    charge = services.recurring.create(
        charge_draft(services, pesos.id, ars("100"), date.today(), name="Netflix")
    )
    event_bus.recurring_changed.emit()
    assert count(offline_window) == "1"
    offline_window.open_notifications()

    open_row(offline_window.notification_panel.rows[0])
    assert offline_window.current_page is offline_window.page(PageId.RECURRING)

    services.recurring.pay(charge.id, ars("100"), date.today(), pesos.id)
    event_bus.recurring_changed.emit()
    assert not offline_window.top_bar.notification_count.isVisibleTo(offline_window)


def test_budget_notice_appears_when_an_expense_passes_the_limit(
    qtbot, services, event_bus, offline_window, pesos
):
    food = category_id(services, "Supermercado y comida", TransactionType.EXPENSE)
    services.budgets.set_limit(food, Month.of(date.today()), ars("100"))
    services.transactions.create(
        expense_draft(services, pesos.id, ars("150"), on=date.today(), category_id=food)
    )
    event_bus.transactions_changed.emit()
    assert count(offline_window) == "1"
    offline_window.open_notifications()

    open_row(offline_window.notification_panel.rows[0])

    assert offline_window.current_page is offline_window.page(PageId.BUDGETS)


class TestBackupReminder:
    @pytest.fixture
    def reminded_window(self, database, pesos, offline_window, event_bus):
        data_since(database, date(2000, 1, 1))
        event_bus.backups_changed.emit()
        assert count(offline_window) == "1"
        offline_window.open_notifications()
        row = offline_window.notification_panel.rows[0]
        assert main_action(row.actions()) == "Guardar copia…"
        return offline_window

    def test_put_off_with_ahora_no(self, reminded_window):
        row = reminded_window.notification_panel.rows[0]

        run_action(row.actions(), "Ahora no: avisar a fin del mes que viene")

        assert count(reminded_window) == ""

    def test_saving_the_copy_clears_it(self, monkeypatch, tmp_path, services, reminded_window):
        monkeypatch.setattr(
            external_backup.QFileDialog, "getExistingDirectory", lambda *_a: str(tmp_path)
        )

        open_row(reminded_window.notification_panel.rows[0])

        assert services.backups.last_external_backup() == date.today()
        assert count(reminded_window) == ""


class TestSeen:
    """The bell counts what the user has not opened; the panel marks it with a dot."""

    @pytest.fixture
    def over_budget(self, services, event_bus, offline_window, pesos):
        """Passes a budget and returns a function that passes another one."""

        def pass_budget(name):
            category = category_id(services, name, TransactionType.EXPENSE)
            services.budgets.set_limit(category, Month.of(date.today()), ars("10"))
            services.transactions.create(
                expense_draft(services, pesos.id, ars("20"), on=date.today(), category_id=category)
            )
            event_bus.transactions_changed.emit()

        pass_budget("Ocio")
        return pass_budget

    def test_opening_the_bell_does_not_count_as_seeing(self, offline_window, over_budget):
        offline_window.open_notifications()

        row = offline_window.notification_panel.rows[0]
        assert count(offline_window) == "1"
        assert row.dot.color() != ""
        assert row.accessibleName().startswith("Sin revisar: ")
        assert offline_window.notification_panel.unseen_label.text() == "1 sin revisar"

    def test_a_click_marks_it_seen_and_it_stays_listed(self, offline_window, over_budget):
        offline_window.open_notifications()

        open_row(offline_window.notification_panel.rows[0])

        assert count(offline_window) == ""
        offline_window.open_notifications()
        row = offline_window.notification_panel.rows[0]
        assert row.notice.seen and row.dot.color() == ""
        assert offline_window.notification_panel.unseen_label.text() == ""

    def test_something_new_lights_it_again(self, offline_window, over_budget):
        offline_window.open_notifications()
        open_row(offline_window.notification_panel.rows[0])

        over_budget("Ropa")

        assert count(offline_window) == "1"

    def test_what_was_seen_stays_seen_after_a_restart(
        self, qtbot, services, event_bus, theme_manager, offline_window, over_budget
    ):
        offline_window.open_notifications()
        open_row(offline_window.notification_panel.rows[0])

        window = MainWindow(services, event_bus, theme_manager)
        qtbot.addWidget(window)

        assert count(window) == ""

    def test_a_menu_without_ways_to_put_it_away(self, offline_window, over_budget):
        offline_window.open_notifications()

        assert texts(offline_window.notification_panel.rows[0].actions()) == ["Ver presupuestos"]


@pytest.mark.parametrize("kind", list(NoticeKind))
def test_every_kind_of_notice_has_its_row(kind):
    """A new kind of notice says where its click leads and, if it can be put away, how."""
    behavior = NOTICES[kind]
    assert behavior.action_text
    assert (behavior.dismiss_text is None) == (behavior.dismiss is None)
