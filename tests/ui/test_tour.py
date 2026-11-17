"""The guided tour points at what is on Inicio, moves with the keys, and is offered once."""

import pytest
from boxes import answer_box
from PySide6.QtCore import Qt

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.ui.shell import main_window
from nodus.ui.shell.coach_marks import CoachMarks
from nodus.ui.shell.main_window import MainWindow
from nodus.ui.shell.tour import TOUR_STEPS


@pytest.fixture
def tour(window, pesos) -> CoachMarks:
    return window.start_tour()


def test_every_step_points_at_something_on_screen(tour):
    """A widget renamed or moved would leave its step out, and this would fail."""
    assert [step.target for step in tour.steps] == [step.target for step in TOUR_STEPS]
    for index in range(len(tour.steps)):
        tour.index = index
        assert not tour.hole().isEmpty()
        assert tour.rect().contains(tour.bubble.geometry())


def test_buttons_go_forward_and_back(tour):
    assert tour.count_label.text() == f"1 de {len(TOUR_STEPS)}"
    assert not tour.back_button.isEnabled()

    tour.next_button.click()
    assert tour.index == 1
    tour.back_button.click()
    assert tour.index == 0


def test_the_last_step_ends_it(qtbot, tour):
    finished = []
    tour.finished.connect(lambda: finished.append(True))
    for _ in TOUR_STEPS[:-1]:
        tour.next_button.click()

    assert tour.next_button.text() == "Terminar"
    assert not tour.skip_button.isVisible()
    tour.next_button.click()
    assert finished == [True]


def test_keys_move_and_esc_skips(qtbot, tour):
    finished = []
    tour.finished.connect(lambda: finished.append(True))

    qtbot.keyClick(tour, Qt.Key.Key_Right)
    qtbot.keyClick(tour, Qt.Key.Key_Return)
    assert tour.index == 2
    qtbot.keyClick(tour, Qt.Key.Key_Left)
    assert tour.index == 1
    qtbot.keyClick(tour, Qt.Key.Key_Escape)
    assert finished == [True]


def test_a_hidden_target_leaves_its_step_out(window, pesos):
    window.sidebar.set_collapsed(True)

    tour = window.start_tour()

    assert "accounts" not in [step.target for step in tour.steps]


class TestOffer:
    @pytest.fixture
    def asked(self, monkeypatch) -> list[str]:
        """The questions asked, answered «Ahora no»; the tour itself is never started."""
        questions = []
        monkeypatch.setattr(
            main_window, "ask", lambda _parent, _title, text, *_: questions.append(text)
        )
        return questions

    @pytest.fixture
    def fresh_window(self, qtbot, services, event_bus, theme_manager):
        window = MainWindow(services, event_bus, theme_manager)
        qtbot.addWidget(window)
        window.show()
        return window

    def test_offered_after_the_first_account_only(
        self, qtbot, services, event_bus, fresh_window, asked
    ):
        fresh_window.show_unseen_news()
        assert asked == []  # no account yet

        services.accounts.create("Banco", AccountType.BANK, Currency.ARS, Money(0, Currency.ARS))
        event_bus.accounts_changed.emit()
        qtbot.waitUntil(lambda: len(asked) == 1)

        event_bus.accounts_changed.emit()
        fresh_window.show_unseen_news()
        qtbot.wait(10)
        assert asked == ["¿Te muestro cómo se usa Nodus? Es un minuto."]

    def test_offered_to_someone_updating_after_the_news(
        self, services, pesos, fresh_window, asked, monkeypatch
    ):
        monkeypatch.setattr(services.news, "take_unseen", lambda: ["1.7.0"])
        monkeypatch.setattr(main_window.NewsDialog, "for_entries", lambda *a, **k: news_dialog)

        class news_dialog:  # noqa: N801
            exec = staticmethod(lambda: asked.append("news"))

        fresh_window.show_unseen_news()
        fresh_window.show_unseen_news()

        assert asked == ["news", "¿Te muestro cómo se usa Nodus? Es un minuto.", "news"]
        assert services.settings.tour_offered()

    @pytest.mark.parametrize("how", ["Ahora no", "Esc"])
    def test_no_with_the_real_box_starts_nothing(self, services, pesos, fresh_window, how):
        answer_box(how)

        fresh_window.offer_tour()

        assert getattr(fresh_window, "tour", None) is None
        assert services.settings.tour_offered()

    def test_yes_starts_it(self, services, pesos, fresh_window, monkeypatch):
        monkeypatch.setattr(main_window, "ask", lambda *args: True)

        fresh_window.offer_tour()

        assert fresh_window.tour.isVisible()
        assert fresh_window.current_page is fresh_window.page(main_window.PageId.DASHBOARD)


def test_settings_opens_it(window, pesos):
    window.show_page(main_window.PageId.SETTINGS)

    window.page(main_window.PageId.SETTINGS).tour_requested.emit()

    assert window.tour.isVisible()
    assert window.current_page is window.page(main_window.PageId.DASHBOARD)
