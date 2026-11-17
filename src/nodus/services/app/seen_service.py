"""The one record of what the user has already seen."""

from __future__ import annotations

from collections.abc import Iterable

from nodus.services.app.settings_service import SettingsService


class SeenService:
    """What the user has already seen, by key: each item a notice is about (a charge on
    its due date, a budget in its month) has one. The bell and «Ya lo vi» on a charge
    read and write here, so seeing something in one place shows it seen in every other.

    A key names the item and its state ("charge:3@2026-11-20:soon"), so when the state
    changes the item is new again on its own, without forgetting anything.
    """

    def __init__(self, settings: SettingsService) -> None:
        self._settings = settings

    def all(self) -> set[str]:
        return self._settings.seen_notices()

    def is_seen(self, key: str) -> bool:
        return key in self.all()

    def mark(self, keys: Iterable[str]) -> None:
        self._save(self.all() | set(keys))

    def unmark(self, keys: Iterable[str]) -> None:
        self._save(self.all() - set(keys))

    def keep_only(self, keys: set[str]) -> None:
        """Forgets what no longer applies, so the record stays as short as the day's
        notices; saves only when something changed."""
        seen = self.all()
        if seen - keys:
            self._save(seen & keys)

    def _save(self, keys: set[str]) -> None:
        if keys != self.all():
            self._settings.set_seen_notices(keys)
