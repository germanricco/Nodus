"""What changed since the version the user opened last, shown once after an update."""

from __future__ import annotations

from collections.abc import Callable

from nodus.services.changelog import ChangelogEntry, entries_between, load_changelog
from nodus.services.settings_service import SettingsService
from nodus.services.update_service import parse_version

# The last version that did not record which news the user saw. An existing data file
# without that record comes from it (or an older one), so it is shown what came after.
VERSION_BEFORE_NEWS = "1.0.1"


class NewsService:
    """Decides which changelog entries to show when Nodus opens, and remembers it did."""

    def __init__(
        self,
        settings: SettingsService,
        current_version: str,
        first_start: bool,
        changelog: Callable[[], list[ChangelogEntry]] = load_changelog,
    ) -> None:
        self._settings = settings
        self._current_version = current_version
        self._first_start = first_start
        self._changelog = changelog

    def all_entries(self) -> list[ChangelogEntry]:
        """Every version up to the running one, newest first, for Ajustes."""
        return entries_between(self._changelog(), "0", self._current_version)

    def take_unseen(self) -> list[ChangelogEntry]:
        """The entries the user has not seen yet; from now on they count as seen.

        A first start shows nothing: everything is new, and there is no update to tell.
        """
        last_seen = self._settings.last_seen_version()
        if last_seen is None and self._first_start:
            self._settings.set_last_seen_version(self._current_version)
            return []
        if last_seen is None or not _is_version(last_seen):
            last_seen = VERSION_BEFORE_NEWS
        if parse_version(last_seen) >= parse_version(self._current_version):
            return []
        self._settings.set_last_seen_version(self._current_version)
        return entries_between(self._changelog(), last_seen, self._current_version)


def _is_version(text: str) -> bool:
    try:
        parse_version(text)
    except ValueError:
        return False
    return True
