"""The proportion bar, painted directly so it follows the theme and animates."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from nodus.ui.theme.design import Chart
from nodus.ui.theme.theme import Theme
from nodus.ui.widgets.charts.chart_base import AnimatedChart, lerp, starting_values


@dataclass(frozen=True)
class Segment:
    """A slice of a chart: its color and size (any unit, only proportions matter).

    ``key`` lets a slice keep its identity between updates, so it can grow or shrink
    instead of jumping; ``label``, ``amount_text`` and ``share_text`` are shown in the
    middle of the ring while the slice is under the mouse.
    """

    color: str
    value: int
    key: str = ""
    label: str = ""
    amount_text: str = ""
    share_text: str = ""


class ProportionBar(AnimatedChart):
    """A thin horizontal bar split between segments, e.g. income against expenses.

    Its parts slide to their new widths when the figures change.
    """

    HEIGHT = Chart.PROPORTION_HEIGHT

    def __init__(
        self, theme: Theme, segments: list[Segment] | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(theme, parent)
        self._segments: list[Segment] = []
        self._previous: list[float] = []
        self.make_strip(self.HEIGHT)
        if segments:
            self.set_segments(segments)

    def set_segments(self, segments: list[Segment]) -> None:
        if segments == self._segments:
            return
        shares = self._shares(self.progress)
        shown = dict(zip((s.key for s in self._segments), shares, strict=True))
        # Each part slides from its width on screen; a new one grows from nothing. The
        # first time, the parts grow from the left together.
        self._previous = starting_values(shown, [s.key for s in segments], 0.0) if shown else []
        self._segments = segments
        self._start_transition()

    def _shares(self, progress: float) -> list[float]:
        """Each segment's fraction of the bar at this point of the transition."""
        total = sum(max(0, s.value) for s in self._segments)
        targets = [max(0, s.value) / total if total else 0.0 for s in self._segments]
        if len(self._previous) != len(targets):
            # Without a previous state the parts grow from the left together.
            return [share * progress for share in targets]
        return [lerp(a, b, progress) for a, b in zip(self._previous, targets, strict=True)]

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        radius = self.HEIGHT / 2
        painter.setBrush(QColor(self._theme.border))
        painter.drawRoundedRect(QRectF(self.rect()), radius, radius)
        shares = self._shares(self.progress)
        visible = [(s, share) for s, share in zip(self._segments, shares, strict=True) if share > 0]
        left = 0.0
        gap = 3 if len(visible) > 1 else 0
        for index, (segment, share) in enumerate(visible):
            width = self.width() * share
            is_last = index == len(visible) - 1
            painter.setBrush(QColor(segment.color))
            painter.drawRoundedRect(
                QRectF(left, 0, max(0.0, width - (0 if is_last else gap)), self.HEIGHT),
                radius,
                radius,
            )
            left += width
        painter.end()
