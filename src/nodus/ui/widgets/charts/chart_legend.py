"""What each color of a chart stands for, beside its title."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtWidgets import QHBoxLayout, QWidget

from nodus.i18n import _
from nodus.ui.theme.design import ControlSize, Space
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.color_dot import ColorDot
from nodus.ui.widgets.style import muted_label

# A name and how to read its color from the theme, so the legend follows it as the chart does.
Entry = tuple[str, Callable[[Theme], str]]


class ChartLegend(QWidget):
    """ "● Ingresos  ● Gastos": a dot in each color and its name, in one line."""

    def __init__(self, entries: Sequence[Entry], theme_manager: ThemeManager) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.M)
        self._dots: list[tuple[ColorDot, Callable[[Theme], str]]] = []
        for name, color_of in entries:
            item = QHBoxLayout()
            item.setSpacing(Space.XS)
            dot = ColorDot(size=ControlSize.DOT_SMALL)
            item.addWidget(dot)
            item.addWidget(muted_label(name))
            layout.addLayout(item)
            self._dots.append((dot, color_of))
        self._apply_theme(theme_manager.theme)
        theme_manager.theme_changed.connect(self._apply_theme)

    def _apply_theme(self, theme: Theme) -> None:
        for dot, color_of in self._dots:
            dot.set_color(color_of(theme))


def income_expense_legend(theme_manager: ThemeManager) -> ChartLegend:
    """The legend of the income and expense bars (``BarChart``)."""
    return ChartLegend(
        [(_("Ingresos"), lambda theme: theme.income), (_("Gastos"), lambda theme: theme.expense)],
        theme_manager,
    )
