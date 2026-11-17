import pytest

from nodus.models.palette import PALETTE
from nodus.services import settings_service


def test_theme_preference_is_saved_and_replaced(services):
    assert services.settings.theme_preference() is None

    services.settings.set_theme_preference("dark")
    services.settings.set_theme_preference("light")

    assert services.settings.theme_preference() == "light"


def test_data_file_is_the_open_database(services, database):
    assert services.settings.data_file == database.path


def test_update_check_is_on_until_turned_off(services):
    assert services.settings.check_updates()

    services.settings.set_check_updates(False)
    assert not services.settings.check_updates()

    services.settings.set_check_updates(True)
    assert services.settings.check_updates()


def test_last_account_is_remembered(services):
    assert services.settings.last_account_id() is None

    services.settings.set_last_account_id(7)

    assert services.settings.last_account_id() == 7


@pytest.mark.parametrize("windows_animates", [True, False])
def test_reduce_motion_follows_windows_until_chosen(services, monkeypatch, windows_animates):
    monkeypatch.setattr(settings_service, "windows_animations_on", lambda: windows_animates)
    assert services.settings.reduce_motion() is not windows_animates

    services.settings.set_reduce_motion(windows_animates)

    assert services.settings.reduce_motion() is windows_animates


@pytest.mark.parametrize("months", [6, 12, None])
def test_the_account_chart_range_is_remembered(services, months):
    assert services.settings.account_chart_months() == 12  # a year until chosen

    services.settings.set_account_chart_months(months)

    assert services.settings.account_chart_months() == months


class TestRecentColors:
    def test_the_latest_first_without_repeats(self, services):
        for color in ("#111111", "#222222", "#111111"):
            services.settings.add_recent_color(color)

        assert services.settings.recent_colors() == ["#111111", "#222222"]

    def test_only_the_last_few_are_kept(self, services):
        for index in range(settings_service.RECENT_COLORS + 2):
            services.settings.add_recent_color(f"#00000{index}")

        recent = services.settings.recent_colors()
        assert len(recent) == settings_service.RECENT_COLORS
        assert recent[0] == f"#00000{settings_service.RECENT_COLORS + 1}"

    def test_palette_colors_are_always_at_hand_and_not_kept(self, services):
        services.settings.add_recent_color(PALETTE[0].upper())

        assert services.settings.recent_colors() == []
