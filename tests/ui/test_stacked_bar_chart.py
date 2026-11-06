"""The stacked bars of the analysis trends."""

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt

from nodus.ui.theme.theme import LIGHT
from nodus.ui.widgets.stacked_bar_chart import StackedBar, StackedBarChart, StackSegment

# The chart is 400 x 260 and its bars sit between TOP (18) and 260 - BOTTOM (22).
WIDTH, HEIGHT = 400, 260


def bar(label: str, *pieces: tuple[int, float]) -> StackedBar:
    segments = tuple(StackSegment(key, f"#00{key:02d}00", value) for key, value in pieces)
    return StackedBar(label, segments, label, ())


def make_chart(qtbot) -> StackedBarChart:
    chart = StackedBarChart(LIGHT, lambda cents: f"$ {cents / 100:.0f}")
    qtbot.addWidget(chart)
    chart.resize(WIDTH, HEIGHT)
    chart.show()
    qtbot.waitExposed(chart)
    return chart


def test_pieces_stack_from_the_baseline(qtbot):
    chart = make_chart(qtbot)
    chart.set_bars([bar("Oct", (1, 300), (2, 100)), bar("Nov", (1, 200))])

    baseline, per_cent = chart._scale(chart._values_at(1))
    pieces = chart._pieces(0, [300, 100], baseline, per_cent)

    assert baseline == pytest.approx(HEIGHT - StackedBarChart.BOTTOM)  # nothing negative
    first, second = (rect for _segment, rect in pieces)
    assert first.bottom() == pytest.approx(baseline)
    assert second.bottom() == pytest.approx(first.top())
    assert second.top() == pytest.approx(StackedBarChart.TOP)  # the tallest bar fills the room


def test_negative_bars_hang_below_the_baseline(qtbot):
    chart = make_chart(qtbot)
    chart.set_bars([bar("Oct", (1, 300)), bar("Nov", (1, -100))])

    baseline, per_cent = chart._scale(chart._values_at(1))
    ((_segment, rect),) = chart._pieces(1, [-100], baseline, per_cent)

    assert rect.top() == pytest.approx(baseline)
    assert rect.height() == pytest.approx(100 * per_cent)
    assert rect.bottom() == pytest.approx(HEIGHT - StackedBarChart.BOTTOM)


def test_average_line_widens_the_scale(qtbot):
    chart = make_chart(qtbot)
    chart.set_bars([bar("Oct", (1, 100))], average=200)

    baseline, per_cent = chart._scale(chart._values_at(1))

    assert baseline - 200 * per_cent == pytest.approx(StackedBarChart.TOP)
    chart.grab()


def test_pieces_resize_by_category_and_new_months_grow(qtbot):
    chart = make_chart(qtbot)
    chart.set_bars([bar("Oct", (1, 100), (2, 50))])

    chart.set_bars([bar("Oct", (2, 150), (3, 40))])
    assert chart._values_at(0.5) == [[100, 20]]  # 2 goes 50 → 150, 3 grows from 0

    chart.set_bars([bar("Oct", (1, 10)), bar("Nov", (1, 20))])
    assert chart._values_at(0.5) == [[5], [10]]


def test_click_reports_the_month_and_category(qtbot):
    chart = make_chart(qtbot)
    chart.set_bars([bar("Oct", (1, 300), (2, 100)), bar("Nov", (1, 200))])
    baseline, _per_cent = chart._scale(chart._values_at(1))
    oct_x = WIDTH / 4

    assert chart.segment_at(QPointF(oct_x, baseline - 5)) == (0, 1)
    assert chart.segment_at(QPointF(oct_x, StackedBarChart.TOP + 5)) == (0, 2)
    with qtbot.waitSignal(chart.clicked) as clicked:
        qtbot.mouseClick(chart, Qt.MouseButton.LeftButton, pos=QPoint(int(oct_x), 5))
    assert clicked.args == [0, None]  # above the bar: the whole month

    qtbot.mouseMove(chart, QPoint(int(WIDTH * 0.75), 100))
    assert chart.hover_index == 1
    chart.grab()
