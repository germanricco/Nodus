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
