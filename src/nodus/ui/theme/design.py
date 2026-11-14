"""Nodus's design scale: the typeface, text sizes, spacing, corners and every other
measure of the interface: icons, controls, lines, windows and charts.

Each text plays a named role and each measure takes a named step instead of a number of
its own, so every page looks alike and the whole look changes from here: another
typeface, roomier cards, rounder corners, larger icons. The stylesheet refers to the
scale as tokens (``$title_size``, ``$space_m``, ``$icon_s``, ``$field_height``); Python
code uses the classes below and ``role_font``. Only the geometry of a single drawing (the
proportions of a chart, the dots of a grip) stays in its widget, marked ``# geometry``.
Light and dark themes share this scale; only colors differ between them (``theme.py``).
"""

from __future__ import annotations

from enum import Enum, IntEnum

from PySide6.QtCore import QEasingCurve
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
    LABEL = (9, SEMIBOLD)  # card titles, sidebar sections, table headers

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


class IconSize(IntEnum):
    """Icons, and indicators drawn as one (arrows, check boxes), as squares in pixels:
    the larger the control, the larger its icon."""

    XS = 12  # the arrow of the calendar's month
    S = 14  # the arrow of a list or of the period button
    M = 16  # check boxes
    L = 18  # an icon in a small button or beside a label: «+», «⋯», pay, collapse
    XL = 20  # the icons of the sidebar and the top bar, and the way back


class ControlSize:
    """Controls in pixels: fields, buttons and the parts of lists, bars and sliders.
    Round and square controls give one side."""

    FIELD_HEIGHT = 24  # a field's text line, inside its padding
    DROP_DOWN_WIDTH = 24  # the arrow's box at the right end of a list
    AMOUNT_SYMBOL_WIDTH = 28  # «$» or «US$» before an amount
    SMALL_BUTTON = 28  # a row's «⋯» and pay buttons
    COLLAPSE_BUTTON = 34  # the sidebar's
    BACK_BUTTON = 36  # the way back of a detail page
    TOP_BAR_BUTTON = 38
    BADGE = 32  # an account's initials
    NOTIFICATION_COUNT = 18  # the count over the bell
    LOGO = 28
    PERIOD_BUTTON_MIN_WIDTH = 130  # so the arrows around it stay put between months
    COLOR_SWATCH = 26
    COLOR_PREVIEW = 28  # the chosen color beside the wheel
    COLOR_WHEEL = 180
    TOGGLE_WIDTH = 40
    TOGGLE_HEIGHT = 22
    PROGRESS_HEIGHT = 8  # a progress bar: an update's download, a budget
    SCROLL_BAR_WIDTH = 10
    SCROLL_HANDLE_MIN_LENGTH = 24
    SLIDER_GROOVE = 6
    SLIDER_HANDLE = 16


class Line:
    """Lines in pixels, and how strong the soft ones are."""

    THIN = 1  # dividers, borders, chart grids
    STROKE = 1.5  # the strokes of an icon drawn in code: ticks, a crossed-out switch
    THICK = 2  # the chosen tab's mark, where a dragged row lands, a budget's pace
    DATA = 2.5  # the line of a line chart
    MARK = 3  # the point of a line under the mouse
    SOFT_ALPHA = 90  # opacity (of 255) of a divider inside a list, softer than a border


class Opacity:
    """How opaque a drawn shape is, from 0 to 1, where the theme's colors alone cannot
    say it: a bar that steps back, a fill that fades."""

    FADED = 0.35  # bars and slices other than the one pointed at
    BAR = 0.9  # a chart bar at rest
    OVER = 0.3  # the part of a budget beyond its limit
    GRID = 0.8  # chart grid lines
    AREA = 0.32  # the top of the area under a line, which fades out downwards
    GUIDE = 0.7  # the line that follows the mouse across a chart
    DISABLED = 0.4  # a control that cannot be used
    DRAGGED = 0.85  # a row on the move, so where it lands shows beneath it


class Motion(IntEnum):
    """How long a change takes on screen, in milliseconds: quick for an answer to the
    mouse, slower for data that changes, so the eye can follow it. ``motion_ms`` gives
    the length to use, which is 0 when the user asked for less motion."""

    FAST = 160  # a slice that grows under the mouse
    SLOW = 450  # charts and figures moving to new data


class Easing:
    """The curve of each kind of motion."""

    SETTLE = QEasingCurve.Type.OutCubic  # fast, then slowing into place
    POP = QEasingCurve.Type.OutBack  # overshoots a little, for what answers the mouse


class _MotionPreference:
    """Whether the user asked for less motion; read on every transition, so a change
    applies at once."""

    reduced = False


def set_reduced_motion(reduced: bool) -> None:
    """Turns every transition into a jump to its end (the «Reducir animaciones» choice)."""
    _MotionPreference.reduced = reduced


def motion_ms(step: Motion) -> int:
    """How long ``step`` lasts now: 0 when motion is reduced."""
    return 0 if _MotionPreference.reduced else int(step)


class Layout:
    """Windows, panels and the widths given by hand, in pixels."""

    WINDOW_MIN_SIZE = (1100, 700)
    DETAIL_LIST_MIN_HEIGHT = 360  # the movements on an account's page; the page scrolls
    WINDOW_SIZE = (1280, 800)  # on first opening
    NARROW_WIDTH = 900  # below it, the Dashboard stacks its cards
    SIDEBAR_WIDTH = 260
    SIDEBAR_COLLAPSED_WIDTH = 64
    HEADER_HEIGHT = 44  # a page's title row
    DIALOG_MIN_WIDTH = 460  # a form
    MESSAGE_MIN_WIDTH = 420  # a dialog of text and buttons, such as an update's
    NEWS_SIZE = (560, 520)
    PICKER_MIN_SIZE = (780, 520)  # a dialog built around a table, such as the refund's
    NOTIFICATION_PANEL_WIDTH = 340
    SEARCH_WIDTH = 200
    SEARCH_MIN_WIDTH = 140  # beside the filters of Transacciones
    NUMBER_FIELD_WIDTH = 200  # a rate
    HEX_FIELD_WIDTH = 100
    DAY_FIELD_MIN_WIDTH = 90
    LEGEND_MIN_WIDTH = 300  # a chart's legend beside it; with less room it goes below
    CHANGE_BADGE_MIN_WIDTH = 64
    LIST_MIN_CHARACTERS = 14  # how wide a selector is, in characters of its names
    LIST_INDENT = 18  # a subcategory in a list
    TREE_INDENT = 28  # a subcategory in Categorías, which has room for more
    CHECK_COLUMN = 34  # a table's check boxes
    MORE_COLUMN = 32  # a table's «⋯»


class Chart:
    """Charts in pixels: the size each asks for, and the measures of its marks."""

    BAR_SIZE = (320, 150)
    BAR_MIN_HEIGHT = 120
    BAR_MAX_WIDTH = 22
    BAR_PAIR_GAP = 3  # between the income and expense bars of a month
    STACKED_SIZE = (480, 260)
    STACKED_MIN_HEIGHT = 220
    STACKED_BAR_MAX_WIDTH = 34
    LINE_SIZE = (480, 220)
    LINE_MIN_HEIGHT = 180
    ACCOUNT_HEIGHT = 200  # an account's balance over time
    DONUT_SIZE = 240
    DONUT_MIN_SIZE = 200
    DONUT_THICKNESS = 26
    DONUT_POP = 8  # how far the slice under the mouse grows
    PROPORTION_HEIGHT = 10  # the bar split between income and expenses


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
    DIVIDER_HEIGHT = 2 * DIVIDER_MARGIN + Line.THIN
    # A calendar's day: a square big enough to click, and the room around the chosen one.
    CALENDAR_CELL = Space.XXXL
    CALENDAR_CELL_GAP = Space.XXS
    # Between a field and what opens under it: a panel, or a menu that reads as its own.
    PANEL_OFFSET = 6
    MENU_OFFSET = Space.XXS


def _measures(scale: type) -> list[tuple[str, int]]:
    """The named measures of a class of the scale."""
    return [(name, value) for name, value in vars(scale).items() if name.isupper()]


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
    ``<role>_weight`` for each text role, ``space_<step>``, ``radius_<step>``,
    ``icon_<step>``, each ``ControlSize`` in lowercase (``field_height``…),
    ``line_thin`` and ``line_thick``, and the ``Popup`` steps (``popup_padding``…)."""
    tokens = {"font_family": f'"{FONT_FAMILY}"'}
    for role in TextRole:
        name = role.name.lower()
        tokens[f"{name}_size"] = f"{role.size}pt"
        tokens[f"{name}_weight"] = str(role.weight)
    tokens.update({f"space_{step.name.lower()}": f"{step}px" for step in Space})
    tokens.update({f"radius_{step.name.lower()}": f"{step}px" for step in Radius})
    tokens.update({f"icon_{step.name.lower()}": f"{step}px" for step in IconSize})
    tokens.update({name.lower(): f"{value}px" for name, value in _measures(ControlSize)})
    tokens.update(line_thin=f"{Line.THIN}px", line_thick=f"{Line.THICK}px")
    tokens.update(
        popup_padding=f"{Popup.PADDING}px",
        popup_radius=f"{Popup.RADIUS}px",
        popup_item_radius=f"{Popup.ITEM_RADIUS}px",
        list_item_padding=_padding(Popup.LIST_ITEM_PADDING),
        menu_item_padding=_padding(Popup.MENU_ITEM_PADDING),
        popup_divider_margin=f"{Popup.DIVIDER_MARGIN}px",
    )
    return tokens
