"""Nodus's design scale: the typeface, text sizes, spacing and corners every screen
picks from.

Each text plays a named role and each gap or corner takes a named step instead of a
number of its own, so every page looks alike and the whole look changes from here:
another typeface, roomier cards, rounder corners. The stylesheet refers to the scale as
tokens (``$title_size``, ``$space_m``, ``$radius_l``); Python code uses ``Space``,
``Radius`` and ``role_font``. Light and dark themes share this scale; only colors differ
between them (``theme.py``).
"""

from __future__ import annotations

from enum import Enum, IntEnum

from PySide6.QtGui import QFont

FONT_FAMILY = "Segoe UI"

REGULAR, SEMIBOLD, BOLD = 400, 600, 700


class TextRole(Enum):
    """A kind of text, with its size in points and its weight. Captions (``LABEL``) are
    also written in capitals."""

    DISPLAY = (28, BOLD)  # the one figure a page is about: the net worth
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


class Space(IntEnum):
    """Gaps and margins in pixels, on a 4 px grid (as Fluent's spacing ramp), plus a
    hairline step for the tightest pairs, such as a value and its caption."""

    XXS = 2
    XS = 4
    S = 8
    M = 12
    L = 16
    XL = 20
    XXL = 24
    XXXL = 32


class Radius(IntEnum):
    """Corner radii in pixels: the larger the surface, the rounder. Something inside
    another rounded thing takes a smaller step, so their corners run parallel. Circles
    and pills take half their height instead."""

    S = 4  # checkboxes, progress bars, chart bars
    M = 6  # fields, segments, menu items: controls inside a larger frame
    L = 8  # buttons, menus, tags, figure tiles
    XL = 12  # cards and panels


class Popup:
    """The spacing of what opens over a page: the lists of a combo box or of suggestions,
    and the menus. Every one takes these steps, so changing one here changes them all."""

    PADDING = Space.XS  # between the frame and its first and last option
    RADIUS = Radius.L  # the frame
    ITEM_RADIUS = Radius.M  # the option under the mouse or chosen
    # (top and bottom, sides). A list is denser than a menu: it may hold many choices.
    LIST_ITEM_PADDING = (Space.XS, Space.M)
    MENU_ITEM_PADDING = (Space.S, Space.M)
    DIVIDER_MARGIN = Space.XS  # above and below the line between groups of options
    DIVIDER_HEIGHT = 2 * DIVIDER_MARGIN + 1


def _padding(steps: tuple[int, int]) -> str:
    return " ".join(f"{step}px" for step in steps)


def role_font(role: TextRole) -> QFont:
    """The font of ``role``, for widgets that paint their own text (charts, delegates)."""
    font = QFont(FONT_FAMILY)
    font.setPointSize(role.size)
    font.setWeight(QFont.Weight(role.weight))
    return font


def design_tokens() -> dict[str, str]:
    """The scale as stylesheet tokens: ``font_family``, ``<role>_size`` and
    ``<role>_weight`` for each text role, ``space_<step>``, ``radius_<step>`` and the
    ``Popup`` steps (``popup_padding``, ``list_item_padding``…)."""
    tokens = {"font_family": f'"{FONT_FAMILY}"'}
    for role in TextRole:
        name = role.name.lower()
        tokens[f"{name}_size"] = f"{role.size}pt"
        tokens[f"{name}_weight"] = str(role.weight)
    tokens.update({f"space_{step.name.lower()}": f"{step}px" for step in Space})
    tokens.update({f"radius_{step.name.lower()}": f"{step}px" for step in Radius})
    tokens.update(
        popup_padding=f"{Popup.PADDING}px",
        popup_radius=f"{Popup.RADIUS}px",
        popup_item_radius=f"{Popup.ITEM_RADIUS}px",
        list_item_padding=_padding(Popup.LIST_ITEM_PADDING),
        menu_item_padding=_padding(Popup.MENU_ITEM_PADDING),
        popup_divider_margin=f"{Popup.DIVIDER_MARGIN}px",
    )
    return tokens
