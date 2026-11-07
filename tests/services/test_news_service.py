import pytest

from nodus.database.database import Database
from nodus.services.changelog import ChangelogEntry
from nodus.services.container import Services
from nodus.services.news_service import VERSION_BEFORE_NEWS, NewsService

CHANGELOG = [
    ChangelogEntry(version, None, f"Novedades de {version}")
    for version in ("1.2.0", "1.1.0", "1.0.1", "1.0.0")
]


def news(services, current: str = "1.1.0", first_start: bool = False) -> NewsService:
    return NewsService(services.settings, current, first_start, lambda: CHANGELOG)


def versions(entries) -> list[str]:
    return [e.version for e in entries]


def test_first_start_shows_nothing_and_remembers_the_version(services):
    service = news(services, first_start=True)

    assert service.take_unseen() == []
    assert services.settings.last_seen_version() == "1.1.0"


def test_update_from_a_version_without_the_record_shows_what_came_after_it(services):
    assert VERSION_BEFORE_NEWS == "1.0.1"

    assert versions(news(services).take_unseen()) == ["1.1.0"]


def test_news_are_shown_only_once(services):
    service = news(services)
    service.take_unseen()

    assert service.take_unseen() == []


def test_jumping_several_versions_shows_all_of_them(services):
    services.settings.set_last_seen_version("1.0.0")

    assert versions(news(services, current="1.2.0").take_unseen()) == ["1.2.0", "1.1.0", "1.0.1"]
    assert services.settings.last_seen_version() == "1.2.0"


def test_going_back_to_an_older_version_shows_nothing_and_keeps_the_record(services):
    services.settings.set_last_seen_version("1.2.0")

    assert news(services).take_unseen() == []
    assert services.settings.last_seen_version() == "1.2.0"


def test_an_unreadable_record_counts_as_the_version_before_news(services):
    services.settings.set_last_seen_version("beta")

    assert versions(news(services).take_unseen()) == ["1.1.0"]


def test_all_entries_stop_at_the_running_version(services):
    assert versions(news(services).all_entries()) == ["1.1.0", "1.0.1", "1.0.0"]


@pytest.mark.parametrize(("reopen", "first_start"), [(False, True), (True, False)])
def test_the_app_knows_whether_this_run_created_the_data_file(tmp_path, reopen, first_start):
    path = tmp_path / "nodus.db"
    if reopen:
        Database.open(path).close()
    database = Database.open(path)
    try:
        assert database.created is first_start
    finally:
        database.close()


def test_a_new_data_file_starts_with_the_news_already_seen(database):
    services = Services.create(database)

    assert services.news.take_unseen() == []
    assert services.settings.last_seen_version() is not None
