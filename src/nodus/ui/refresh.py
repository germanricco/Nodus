"""What a change refreshes, decided in one place.

Every page once listed by hand the changes it shows, and every missing entry was a page
that showed old data until it was opened again: a balance after paying a charge, a name
after merging payees. Here no page lists anything. Any change to the data, or to how
amounts are shown, refreshes what is on screen: the page in view, the accounts of the
sidebar and the bell. A page out of view is refreshed when it is shown
(``MainWindow.show_page``), so the cost is one refresh of one page per change.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import SignalInstance

from nodus.ui.event_bus import EventBus
from nodus.ui.theme.theme_manager import ThemeManager


def screen_signals(event_bus: EventBus) -> list[SignalInstance]:
    """Every signal after which the screen may show something else: each change to the
    stored data, hiding the amounts and the currency of the totals."""
    return [
        *event_bus.data_signals(),
        event_bus.amounts_hidden_changed,
        event_bus.net_worth_currency_changed,
    ]


def refresh_on_changes(
    event_bus: EventBus,
    theme_manager: ThemeManager,
    on_data: Callable[[], None],
    on_theme: Callable[[], None],
) -> None:
    """Calls ``on_data`` after every change in ``screen_signals``, and ``on_theme``
    after the theme changes: a page that paints its rows' colors reads them anew."""
    for signal in screen_signals(event_bus):
        signal.connect(lambda *_args: on_data())
    theme_manager.theme_changed.connect(lambda _theme: on_theme())
