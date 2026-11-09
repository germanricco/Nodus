"""Nodus's design scale: the typeface and the text sizes every screen picks from.

Each text plays a named role instead of choosing its own size, so every page looks alike
and the whole look changes from here: another typeface, or a role a little larger. The
stylesheet refers to the roles as tokens (``$title_size``) and widgets that paint
themselves ask for ``role_font``. Light and dark themes share this scale; only colors
differ between them (``theme.py``).
"""

from __future__ import annotations

from enum import Enum

from PySide6.QtGui import QFont

FONT_FAMILY = "Segoe UI"

REGULAR, SEMIBOLD, BOLD = 400, 600, 700


class TextRole(Enum):
    """A kind of text, with its size in points and its weight. Captions (``LABEL``) are
    also written in capitals."""

    DISPLAY = (28, BOLD)  # the one figure a page is about: an account's balance
    TITLE = (20, SEMIBOLD)  # a page's title
    SUBTITLE = (15, SEMIBOLD)  # a dialog's title, the logo
    FIGURE = (18, SEMIBOLD)  # the value of a figure tile
    FIGURE_SMALL = (13, SEMIBOLD)  # the figures of the Dashboard cards
    STRONG = (11, SEMIBOLD)  # amounts in rows, empty states, the way back
    BODY = (10, REGULAR)  # everything else
    NOTE = (9, REGULAR)  # hints under a field, badges, small buttons, chart axes
    LABEL = (8, SEMIBOLD)  # card titles, sidebar sections, table headers

    @property
    def size(self) -> int:
        return self.value[0]

    @property
    def weight(self) -> int:
        return self.value[1]


def role_font(role: TextRole) -> QFont:
    """The font of ``role``, for widgets that paint their own text (charts, delegates)."""
    font = QFont(FONT_FAMILY)
    font.setPointSize(role.size)
    font.setWeight(QFont.Weight(role.weight))
    return font


def design_tokens() -> dict[str, str]:
    """The scale as stylesheet tokens: ``font_family``, ``<role>_size`` and
    ``<role>_weight`` for each role."""
    tokens = {"font_family": f'"{FONT_FAMILY}"'}
    for role in TextRole:
        name = role.name.lower()
        tokens[f"{name}_size"] = f"{role.size}pt"
        tokens[f"{name}_weight"] = str(role.weight)
    return tokens
