"""Where Alt+← and Alt+→ lead: the pages visited, as a browser keeps them."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from nodus.ui.navigation import DetailId, PageId


@dataclass(frozen=True)
class Place:
    """A page of the sidebar, or the page of one record (``item_id``)."""

    page: PageId | DetailId
    item_id: int | None = None


class NavigationHistory:
    """The places visited before the current one and the ones gone back from.

    A new visit forgets what was ahead, as in a browser. While going back or forward
    (``moving``), a page that leads somewhere else on its own (the page of a record
    deleted since, which goes back to its list) takes the place it was shown for.
    """

    LIMIT = 50

    def __init__(self) -> None:
        self.current: Place | None = None
        self._back: list[Place] = []
        self._forward: list[Place] = []
        self._moving = False

    def visit(self, place: Place) -> None:
        if self._moving:
            self.current = place
            return
        if place == self.current:
            return
        if self.current is not None:
            self._back = [*self._back, self.current][-self.LIMIT :]
        self._forward.clear()
        self.current = place

    def back(self) -> Place | None:
        """The place before, now the current one; ``None`` at the start."""
        if not self._back or self.current is None:
            return None
        self._forward.append(self.current)
        self.current = self._back.pop()
        return self.current

    def forward(self) -> Place | None:
        """The place gone back from, now the current one; ``None`` if there is none."""
        if not self._forward or self.current is None:
            return None
        self._back.append(self.current)
        self.current = self._forward.pop()
        return self.current

    @contextmanager
    def moving(self) -> Iterator[None]:
        self._moving = True
        try:
            yield
        finally:
            self._moving = False
