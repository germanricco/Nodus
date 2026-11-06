from datetime import date

import pytest
from factories import ars
from PySide6.QtCore import QPoint, QPointF, Qt

from nodus.models.currency import Currency
from nodus.ui.theme.theme import LIGHT
from nodus.ui.widgets import chart_base
from nodus.ui.widgets.bar_chart import BarChart, BarGroup
from nodus.ui.widgets.change_badge import ChangeBadge, format_change
from nodus.ui.widgets.chart_base import format_compact, resample
from nodus.ui.widgets.charts import (
    DonutChart,
    ProportionBar,
    Segment,
    clockwise_angle,
    index_at_angle,
    segment_spans,
)
from nodus.ui.widgets.line_chart import (
    LineChart,
    LinePoint,
    axis_indexes,
    change_directions,
    value_range,
)
from nodus.ui.widgets.money_label import AnimatedMoneyLabel

# Pure helpers


def test_resample_stretches_and_shrinks():
    assert resample([0, 10], 3) == [0, 5, 10]
    assert resample([0, 5, 10], 2) == [0, 10]
    assert resample([], 2) == [0, 0]
    assert resample([7], 3) == [7, 7, 7]


@pytest.mark.parametrize(
    ("cents", "currency", "text"),
    [
        (293_827_885, Currency.ARS, "$ 2,9 M"),
        (1_500_000, Currency.USD, "US$ 15 k"),
        (95_000, Currency.ARS, "$ 950"),
        (-120_000_000, Currency.ARS, "-$ 1,2 M"),
        (100_000_000, Currency.ARS, "$ 1 M"),
    ],
)
def test_format_compact(cents, currency, text):
    assert format_compact(cents, currency) == text


def test_value_range_pads_and_handles_flat_series():
    assert value_range([100, 200]) == pytest.approx((88, 212))
    low, high = value_range([500, 500])
    assert low < 500 < high


@pytest.mark.parametrize(
    ("count", "fit", "indexes"),
    [
        (6, 9, [0, 1, 2, 3, 4, 5]),  # every day when all fit: none is skipped
        (30, 9, [0, 4, 8, 12, 16, 20, 24, 29]),  # today replaces a label too close to it
        (30, 6, [0, 5, 10, 15, 20, 25, 29]),
        (1, 9, [0]),
        (0, 9, []),
    ],
)
def test_axis_labels_go_at_a_regular_step_and_end_on_the_last_day(count, fit, indexes):
    assert axis_indexes(count, fit) == indexes


def test_change_directions_skip_unknown_values():
    assert change_directions([1, 2, 2, None, 1, 3]) == [0, 1, 0, 0, -1, 1]


def test_segment_spans_start_at_twelve_and_leave_gaps():
    assert segment_spans([1, 3]) == [(0, 90), (90, 270)]
    assert segment_spans([1, 1], gap=2) == [(1, 178), (181, 178)]
    assert segment_spans([0, 0]) == []


def test_angles_go_clockwise_from_twelve():
    center = QPointF(0, 0)
    assert clockwise_angle(center, QPointF(0, -1)) == pytest.approx(0)
    assert clockwise_angle(center, QPointF(1, 0)) == pytest.approx(90)
    assert clockwise_angle(center, QPointF(-1, 0)) == pytest.approx(270)
    spans = segment_spans([1, 3])
    assert index_at_angle(spans, 45) == 0
    assert index_at_angle(spans, 200) == 1


@pytest.mark.parametrize(
    ("change", "text"), [(0.12, "↗ 12 %"), (-0.095, "↘ 9,5 %"), (0, "→ 0 %"), (0.05, "↗ 5 %")]
)
def test_format_change(change, text):
    assert format_change(change) == text


# Widgets


def test_change_badge_tones(qtbot):
    expenses = ChangeBadge(higher_is_better=False, none_text="Nueva")
    qtbot.addWidget(expenses)

    expenses.set_change(0.2)
    assert expenses.property("tone") == "bad"
    expenses.set_change(-0.2, "−$ 100")
    assert (expenses.text(), expenses.property("tone")) == ("↘ 20 % · −$ 100", "good")
    expenses.set_change(None)
    assert expenses.text() == "Nueva"


def make(qtbot, widget, size=(400, 260)):
    qtbot.addWidget(widget)
    widget.resize(*size)
    widget.show()
    qtbot.waitExposed(widget)
    return widget


def line_points(values):
    return [LinePoint(date(2026, 11, i + 1), v) for i, v in enumerate(values)]


def make_line_chart(qtbot):
    chart = LineChart(LIGHT, str, str, lambda day: f"{day:%d/%m}")
    return make(qtbot, chart)


def test_line_chart_hover_finds_the_nearest_known_point(qtbot):
    chart = make_line_chart(qtbot)
    chart.set_points(line_points([100, None, 300, 200]))

    assert chart.index_at(0) == 0
    assert chart.index_at(chart.width()) == 3
    # The middle-left point is unknown, so the closest known one is chosen.
    plot = chart._plot_rect()
    assert chart.index_at(plot.left() + plot.width() / 3) in (0, 2)

    qtbot.mouseMove(chart, QPoint(chart.width() - 12, 100))
    assert chart.hover_index == 3
    chart.grab()  # paints the hover guide and box without errors


def test_line_chart_morphs_from_the_previous_line(qtbot, monkeypatch):
    chart = make_line_chart(qtbot)
    chart.set_points(line_points([100, 100]))
    monkeypatch.setattr(chart_base, "DURATION_MS", 300)

    chart.set_points(line_points([300, 500]))

    assert chart.progress < 1
    middle = chart._values_at(0.5)
    assert middle == [200, 300]
    qtbot.waitUntil(lambda: chart.progress == 1, timeout=2000)
    assert chart._values_at(chart.progress) == [300, 500]


def test_hidden_chart_plays_its_transition_when_shown(qtbot, monkeypatch):
    monkeypatch.setattr(chart_base, "DURATION_MS", 200)
    chart = BarChart(LIGHT)
    qtbot.addWidget(chart)

    chart.set_groups([BarGroup("Nov", 100, 40, "Noviembre", ("+$ 1",))])

    assert chart.progress == 0
    chart.show()
    qtbot.waitUntil(lambda: chart.progress == 1, timeout=2000)


def test_bars_grow_from_zero_and_keep_place_on_update(qtbot):
    chart = make(qtbot, BarChart(LIGHT))
    chart.set_groups([BarGroup("Oct", 100, 60, "", ()), BarGroup("Nov", 0, 50, "", (), True)])

    chart.set_groups([BarGroup("Oct", 300, 80, "", ()), BarGroup("Nov", 40, 50, "", (), True)])

    assert chart._values_at(0.5) == [(200, 70), (20, 50)]
    assert chart.index_at(chart.width() * 0.75) == 1
    qtbot.mouseMove(chart, QPoint(10, 50))
    assert chart.hover_index == 0
    chart.grab()


def make_donut(qtbot):
    donut = make(qtbot, DonutChart(LIGHT), (260, 260))
    donut.set_data(
        [
            Segment("#ff0000", 100, "a", "Vivienda", "$ 100", "25 %"),
            Segment("#00ff00", 300, "b", "Ocio", "$ 300", "75 %"),
        ],
        "Total",
        ars("400"),
    )
    return donut


def test_donut_click_on_a_slice_emits_its_index(qtbot):
    donut = make_donut(qtbot)
    ring = donut._ring()
    # Just right of 12 o'clock is the first slice; left of it, the second.
    first = QPoint(int(ring.center().x()) + 10, int(ring.top()))
    second = QPoint(int(ring.center().x()) - 10, int(ring.top()))

    assert donut.index_at(QPointF(ring.center())) is None
    with qtbot.waitSignal(donut.segment_clicked) as clicked:
        qtbot.mouseClick(donut, Qt.MouseButton.LeftButton, pos=second)
    assert clicked.args == [1]

    qtbot.mouseMove(donut, first)
    assert donut.hover_index == 0
    donut.grab()


def test_donut_slices_resize_by_key(qtbot):
    donut = make_donut(qtbot)

    donut.set_data(
        [Segment("#00ff00", 100, "b"), Segment("#0000ff", 200, "c")], "Total", ars("300")
    )
    donut.progress = 0.5

    drawn = {segment.key: value for segment, value in donut._drawn()}
    assert drawn == {"b": 200, "c": 100, "a": 50}  # "a" shrinks away, "c" grows in


def test_proportion_bar_slides_to_new_shares(qtbot):
    bar = make(qtbot, ProportionBar(LIGHT, [Segment("#0f0", 1), Segment("#f00", 1)]), (200, 10))

    bar.set_segments([Segment("#0f0", 3), Segment("#f00", 1)])

    assert bar._shares(0.5) == [0.625, 0.375]


def test_animated_money_label_counts_to_the_new_amount(qtbot, monkeypatch):
    label = AnimatedMoneyLabel(ars("100"))
    qtbot.addWidget(label)
    monkeypatch.setattr(chart_base, "DURATION_MS", 200)

    label.set_money(ars("300"))

    assert label.text() != "$ 300,00" or label.money() == ars("300")
    qtbot.waitUntil(lambda: label.text() == "$ 300,00", timeout=2000)
    assert label.money() == ars("300")


def test_money_label_shortens_an_amount_that_does_not_fit(qtbot):
    label = make(qtbot, AnimatedMoneyLabel(compact_when_narrow=True), (60, 20))
    label.set_money(ars("8835000"))

    assert label.text() == "$ 8,8 M"
    assert label.toolTip() == "$ 8.835.000,00"
    # The layout still asks for room for the full figure.
    assert label.minimumSizeHint().width() > 60

    label.resize(400, 20)
    assert label.text() == "$ 8.835.000,00"
