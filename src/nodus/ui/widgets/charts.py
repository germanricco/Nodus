"""Ring and proportion bar, painted directly so they follow the theme and animate."""

from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from nodus.models.money import Money
from nodus.ui.theme.design import Chart, Easing, Motion, Opacity, TextRole, motion_ms, role_font
from nodus.ui.theme.theme import Theme
from nodus.ui.widgets.chart_base import AnimatedChart, lerp, starting_values, with_alpha


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


def segment_spans(
    values: list[float], gap: float = 0.0, whole: float | None = None
) -> list[tuple[float, float]]:
    """(start, span) in degrees for each value, clockwise from 12 o'clock, each slice
    shortened by ``gap`` so neighbours do not touch. The values fill the circle, or the
    share of it they are of ``whole`` when given."""
    total = sum(values) if whole is None else whole
    if total <= 0:
        return []
    spans, start = [], 0.0
    for value in values:
        span = 360.0 * value / total
        spans.append((start + gap / 2, max(0.0, span - gap)))
        start += span
    return spans


def clockwise_angle(center: QPointF, point: QPointF) -> float:
    """Angle of ``point`` around ``center`` in degrees, clockwise from 12 o'clock."""
    dx, dy = point.x() - center.x(), point.y() - center.y()
    return math.degrees(math.atan2(dx, -dy)) % 360


def index_at_angle(spans: list[tuple[float, float]], angle: float) -> int | None:
    for index, (start, span) in enumerate(spans):
        if start <= angle <= start + span:
            return index
    return None


class DonutChart(AnimatedChart):
    """A ring split by segment size, with a caption and the total in the middle.

    The ring sweeps in from 12 o'clock the first time and its slices resize when the data
    changes. The slice under the mouse grows outwards, the others fade and the middle
    shows that slice's name, amount and share; clicking emits ``segment_clicked``.
    """

    THICKNESS = Chart.DONUT_THICKNESS
    POP = Chart.DONUT_POP
    GAP_DEGREES = 1.5  # geometry: between slices

    segment_hovered = Signal(int)  # index, or -1 when none
    segment_clicked = Signal(int)

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(theme, parent)
        self._segments: list[Segment] = []
        self._previous: dict[str, float] = {}
        self._previous_segments: list[Segment] = []
        self._caption = ""
        self._total: Money | None = None
        self._previous_total: Money | None = None
        self._empty_text = ""
        self.hover_index: int | None = None
        self._pop = 1.0
        self._pop_animation = QVariantAnimation(self)
        self._pop_animation.setStartValue(0.0)
        self._pop_animation.setEndValue(1.0)
        self._pop_animation.setEasingCurve(Easing.POP)
        self._pop_animation.valueChanged.connect(self._set_pop)
        self.setMinimumSize(Chart.DONUT_MIN_SIZE, Chart.DONUT_MIN_SIZE)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(Chart.DONUT_SIZE, Chart.DONUT_SIZE)

    def set_data(
        self, segments: list[Segment], caption: str, total: Money | None, empty_text: str = ""
    ) -> None:
        """Shows ``segments`` around ``caption`` and ``total`` (or ``empty_text`` without
        segments), moving from what was shown before."""
        segments = [s for s in segments if s.value > 0]
        unchanged = (segments, caption, total, empty_text) == (
            self._segments, self._caption, self._total, self._empty_text,
        )  # fmt: skip
        if unchanged:
            return
        had_data = bool(self._segments)
        self._previous = self._current_values() if had_data else {}
        self._previous_segments = self._segments if had_data else []
        self._previous_total = self._shown_total() if had_data else None
        self._segments = segments
        self._caption = caption
        self._total = total
        self._empty_text = empty_text
        self.hover_index = None
        self._start_transition()

    def segments(self) -> list[Segment]:
        return self._segments

    def set_highlight(self, index: int | None) -> None:
        """Highlights a slice from outside, e.g. when the mouse is over its legend row."""
        if index == self.hover_index:
            return
        self.hover_index = index
        self._pop_animation.stop()
        self._pop_animation.setDuration(motion_ms(Motion.FAST))
        self._pop_animation.start()
        self.update()

    def _set_pop(self, value: float) -> None:
        self._pop = float(value)
        self.update()

    # Data in transition

    def _keys(self) -> list[str]:
        """Current slices first, then those on their way out."""
        keys = [self._key(s) for s in self._segments]
        leaving = [self._key(s) for s in self._previous_segments if self._key(s) not in keys]
        return keys + leaving

    @staticmethod
    def _key(segment: Segment) -> str:
        return segment.key or segment.color

    def _drawn(self) -> list[tuple[Segment, float]]:
        """Each slice with its size at the current point of the transition."""
        by_key = {self._key(s): s for s in self._previous_segments + self._segments}
        targets = {self._key(s): float(s.value) for s in self._segments}
        if not self._previous or self.progress >= 1:
            return [(s, float(s.value)) for s in self._segments]
        return [
            (by_key[key], lerp(self._previous.get(key, 0.0), targets.get(key, 0.0), self.progress))
            for key in self._keys()
        ]

    def _current_values(self) -> dict[str, float]:
        return {self._key(segment): value for segment, value in self._drawn()}

    def _shown_total(self) -> Money | None:
        if self._total is None or self._previous_total is None or self.progress >= 1:
            return self._total
        cents = lerp(self._previous_total.cents, self._total.cents, self.progress)
        return Money(round(cents), self._total.currency)

    def _spans(self, drawn: list[tuple[Segment, float]]) -> list[tuple[float, float]]:
        """Where each drawn slice goes around the ring. Slices on their way to nothing
        keep their share of what was there, so they shrink away over the empty ring
        instead of filling it until the last frame."""
        gap = self.GAP_DEGREES if len(drawn) > 1 else 0.0
        whole = sum(self._previous.values()) if not self._segments else None
        return segment_spans([value for _segment, value in drawn], gap, whole)

    # Painting

    def _ring(self) -> QRectF:
        side = min(self.width(), self.height()) - self.THICKNESS - 2 * self.POP
        return QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        ring = self._ring()
        self._paint_ring(painter, ring)
        self._paint_center(painter, ring)
        painter.end()

    def _paint_ring(self, painter: QPainter, ring: QRectF) -> None:
        drawn = self._drawn()
        if not self._segments:
            painter.setPen(self._pen(self._theme.border, self.THICKNESS))
            painter.drawEllipse(ring)
        if not drawn:
            return
        spans = self._spans(drawn)
        # First appearance: the ring sweeps in clockwise.
        sweep = 360.0 * self.progress if not self._previous else 360.0
        for index, ((segment, _value), (start, span)) in enumerate(zip(drawn, spans, strict=True)):
            if start >= sweep:
                break
            span = min(span, sweep - start)
            hovered = index == self.hover_index
            faded = self.hover_index is not None and not hovered
            thickness = self.THICKNESS + (self.POP * self._pop if hovered else 0)
            color = with_alpha(segment.color, Opacity.FADED) if faded else QColor(segment.color)
            painter.setPen(self._pen(color, thickness))
            # Qt angles are in 1/16 degree and run counterclockwise from 3 o'clock.
            painter.drawArc(ring, int((90 - start) * 16), int(-span * 16))

    def _paint_center(self, painter: QPainter, ring: QRectF) -> None:
        hovered = (
            self._segments[self.hover_index]
            if self.hover_index is not None and self.hover_index < len(self._segments)
            else None
        )
        if hovered:
            caption, text, extra = hovered.label, hovered.amount_text, hovered.share_text
        elif self._segments:
            total = self._shown_total()
            caption, text, extra = self._caption, total.format() if total else "", ""
        else:
            caption, text, extra = self._caption, self._empty_text, ""
        caption_font = role_font(TextRole.NOTE)
        value_font = role_font(TextRole.FIGURE_SMALL)
        middle = ring.center().y() - (8 if extra else 0)
        inner = ring.adjusted(self.THICKNESS, 0, -self.THICKNESS, 0)
        painter.setPen(QColor(self._theme.text_muted))
        painter.setFont(caption_font)
        painter.drawText(
            QRectF(inner.left(), middle - 26, inner.width(), 20),
            Qt.AlignmentFlag.AlignCenter,
            painter.fontMetrics().elidedText(
                caption, Qt.TextElideMode.ElideRight, int(inner.width())
            ),
        )
        painter.setPen(QColor(self._theme.text))
        painter.setFont(value_font)
        painter.drawText(
            QRectF(ring.left(), middle - 4, ring.width(), 28), Qt.AlignmentFlag.AlignCenter, text
        )
        if extra:
            painter.setPen(QColor(self._theme.text_muted))
            painter.setFont(caption_font)
            painter.drawText(
                QRectF(ring.left(), middle + 26, ring.width(), 20),
                Qt.AlignmentFlag.AlignCenter,
                extra,
            )

    @staticmethod
    def _pen(color: str | QColor, thickness: float) -> QPen:
        pen = QPen(QColor(color), thickness)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        return pen

    # Mouse

    def index_at(self, point: QPointF) -> int | None:
        """The current slice under ``point``, or None off the ring."""
        if not self._segments:
            return None
        ring = self._ring()
        distance = math.dist((point.x(), point.y()), (ring.center().x(), ring.center().y()))
        reach = self.THICKNESS / 2 + self.POP
        if abs(distance - ring.width() / 2) > reach:
            return None
        spans = segment_spans([float(s.value) for s in self._segments])
        return index_at_angle(spans, clockwise_angle(ring.center(), point))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        index = self.index_at(event.position())
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if index is not None else Qt.CursorShape.ArrowCursor
        )
        if index != self.hover_index:
            self.set_highlight(index)
            self.segment_hovered.emit(-1 if index is None else index)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        index = self.index_at(event.position())
        if index is not None and event.button() == Qt.MouseButton.LeftButton:
            self.segment_clicked.emit(index)

    def leaveEvent(self, event) -> None:  # noqa: N802
        super().leaveEvent(event)
        if self.hover_index is not None:
            self.set_highlight(None)
            self.segment_hovered.emit(-1)


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
        self.setFixedHeight(self.HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(False)
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
