"""Helpers to use row menus in tests without opening them."""

from collections.abc import Sequence

from nodus.ui.widgets.row_actions import RowAction


def texts(actions: Sequence[RowAction]) -> list[str]:
    return [action.text for action in actions]


def run_action(actions: Sequence[RowAction], text: str) -> None:
    """Does what choosing the item ``text`` in the menu does."""
    action = next(action for action in actions if action.text == text)
    assert action.enabled, f"«{text}» is disabled"
    action.callback()
