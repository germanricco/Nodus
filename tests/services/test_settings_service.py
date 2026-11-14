import pytest

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
