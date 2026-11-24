from datetime import date

import pytest
from factories import ars
from PySide6.QtCore import QPoint

from nodus.models.currency import Currency
from nodus.ui.theme.theme import LIGHT
from nodus.ui.widgets.change_badge import ChangeBadge, format_change
from nodus.ui.widgets.charts.bar_chart import BarChart, BarGroup
from nodus.ui.widgets.charts.chart_base import (
    compact_pesos,
    distinct_colors,
    format_compact,
    nice_step,
    resample,
    value_axis,
)
from nodus.ui.widgets.charts.line_chart import (
    LineChart,
    LinePoint,
    axis_indexes,
    change_directions,
    height,
    value_range,
)
from nodus.ui.widgets.charts.share_charts import ProportionBar, Segment
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
        (30, 6, [0, 5, 10, 15, 20, 29]),
        (48, 12, [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 47]),
        (1, 9, [0]),
        (0, 9, []),
    ],
)
def test_axis_labels_go_at_a_regular_step_and_end_on_the_last_day(count, fit, indexes):
    assert axis_indexes(count, fit) == indexes


def test_change_directions_skip_unknown_values():
    assert change_directions([1, 2, 2, None, 1, 3]) == [0, 1, 0, 0, -1, 1]


@pytest.mark.parametrize(
    ("change", "text"), [(0.12, "↗ 12 %"), (-0.095, "↘ 9,5 %"), (0, "→ 0 %"), (0.05, "↗ 5 %")]
)
def test_format_change(change, text):
    assert format_change(change) == text


def test_format_change_in_percentage_points():
    assert format_change(-0.05, "pp") == "↘ 5 pp"


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


def heights_at(chart, progress):
    """Where each point is drawn at ``progress``, from 0 at the bottom to 1 at the top."""
    span = chart._range_at(progress)
    return [None if v is None else height(v, span) for v in chart._values_at(progress)]


def test_line_chart_morphs_from_the_previous_line(qtbot, animations):
    chart = make_line_chart(qtbot)
    chart.set_points(line_points([100, 100]))

    chart.set_points(line_points([300, 500]))

    assert chart.progress < 1
    before = [height(100, value_range([100]))] * 2
    after = [height(v, value_range([300, 500])) for v in (300, 500)]
    middle = heights_at(chart, 0.5)
    assert middle == pytest.approx([(b + a) / 2 for b, a in zip(before, after, strict=True)])
    qtbot.waitUntil(lambda: chart.progress == 1, timeout=2000)
    assert chart._values_at(chart.progress) == [300, 500]


def test_line_chart_in_another_currency_keeps_its_place(qtbot):
    """Pesos to dollars changes every value a thousandfold but not the shape: the line
    stays put while the axis changes, instead of sinking and growing back."""
    chart = make_line_chart(qtbot)
    chart.set_points(line_points([3_400_000, 4_100_000, 3_800_000]))
    start = heights_at(chart, 1)

    chart.set_points(line_points([3_400, 4_100, 3_800]))

    for step in range(11):
        assert heights_at(chart, step / 10) == pytest.approx(start)


def test_line_chart_axis_moves_with_the_line(qtbot):
    """A line flattening out flattens on screen: the axis moves from the old span to the
    new one instead of stretching each frame's values to fill the height, which kept the
    old shape until the last frame."""
    chart = make_line_chart(qtbot)
    chart.set_points(line_points([100, 900, 300, 700]))
    chart.set_points(line_points([660, 660, 660, 660]))
    plot = chart._plot_rect()

    def drawn_height(progress):
        ys = [
            p.y()
            for p in chart._positions(chart._values_at(progress), plot, chart._range_at(progress))
        ]
        return max(ys) - min(ys)

    assert chart._range_at(0) == value_range([100, 900, 300, 700])
    heights = [drawn_height(step / 10) for step in range(11)]
    assert heights == sorted(heights, reverse=True) and heights[-1] == 0
    assert heights[5] < heights[0] * 0.7  # flattening shows by halfway
    assert chart._range_at(1) == value_range([660])


def test_line_chart_takes_a_new_period_in_the_middle_of_a_transition(qtbot):
    """Two quick clicks on the period: the second month arrives while the first is
    still moving in, and months of different lengths must not get stuck halfway."""
    chart = make_line_chart(qtbot)
    october = [LinePoint(date(2026, 10, day), 6.6) for day in range(1, 32)]
    november = [LinePoint(date(2026, 11, day), float(day)) for day in range(1, 31)]
    december = [LinePoint(date(2026, 12, day), 9.0) for day in range(1, 32)]
    chart.set_points(october)
    chart.set_points(november)
    chart.progress = 0.4

    chart.set_points(december)

    assert chart.points() == december
    chart.progress = 1
    assert chart._values_at(1) == [9.0] * 31
    chart.grab()


def test_line_chart_starts_each_day_where_it_was_despite_gaps(qtbot):
    """Days without a value (no exchange rate yet) must not shift the others: switching
    the currency of a line with a gap used to start every day from another's value."""
    chart = make_line_chart(qtbot)
    chart.set_points(line_points([None, None, 100, 100, 50]))

    chart.set_points(line_points([None, None, 7, 7, 3]))

    assert chart._values_at(0) == [None, None, 100, 100, 50]  # exactly what was on screen
    assert chart._values_at(0.5) == [None, None, 53.5, 53.5, 26.5]


def test_line_chart_day_that_appears_starts_at_its_new_height(qtbot):
    chart = make_line_chart(qtbot)
    chart.set_points(line_points([None, 100, 200]))

    chart.set_points(line_points([40, 100, 300]))

    assert heights_at(chart, 0)[0] == pytest.approx(height(40, value_range([40, 100, 300])))


def test_line_chart_of_another_period_morphs_by_position(qtbot):
    chart = make_line_chart(qtbot)
    chart.set_points(line_points([100, 300]))

    later = [LinePoint(date(2027, 1, day), 500.0) for day in (1, 2, 3)]
    chart.set_points(later)

    assert chart._values_at(0) == [100, 200, 300]  # the old shape, stretched


def test_hidden_chart_plays_its_transition_when_shown(qtbot, animations):
    chart = BarChart(LIGHT, compact_pesos)
    qtbot.addWidget(chart)

    chart.set_groups([BarGroup("Nov", 100, 40, "Noviembre", ("+$ 1",))])

    assert chart.progress == 0
    chart.show()
    qtbot.waitUntil(lambda: chart.progress == 1, timeout=2000)


def test_bars_grow_from_zero_and_keep_place_on_update(qtbot):
    chart = make(qtbot, BarChart(LIGHT, compact_pesos))
    chart.set_groups([BarGroup("Oct", 100, 60, "", ()), BarGroup("Nov", 0, 50, "", (), True)])

    chart.set_groups([BarGroup("Oct", 300, 80, "", ()), BarGroup("Nov", 40, 50, "", (), True)])

    assert chart._values_at(0.5) == [(200, 70), (20, 50)]
    assert chart.index_at(chart.width() * 0.75) == 1
    qtbot.mouseMove(chart, QPoint(int(chart.LEFT) + 10, 50))  # past the axis' values
    assert chart.hover_index == 0
    chart.grab()


def test_bars_follow_their_month_when_the_period_moves(qtbot):
    """Moving the period one month keeps the count of bars; each must still start from
    its own month, and the month that enters grows from the baseline."""
    chart = make(qtbot, BarChart(LIGHT, compact_pesos))
    chart.set_groups([BarGroup("Oct", 100, 60, "", ()), BarGroup("Nov", 40, 20, "", ())])

    chart.set_groups([BarGroup("Nov", 40, 20, "", ()), BarGroup("Dic", 80, 10, "", ())])

    assert chart._values_at(0) == [(40, 20), (0, 0)]


def test_bars_of_the_same_label_in_another_year_are_other_months(qtbot):
    chart = make(qtbot, BarChart(LIGHT, compact_pesos))
    chart.set_groups([BarGroup("Nov", 100, 60, "", (), key=(2025, 11))])

    chart.set_groups([BarGroup("Nov", 40, 20, "", (), key=(2026, 11))])

    assert chart._values_at(0) == [(0, 0)]


def test_proportion_bar_slides_to_new_shares(qtbot):
    bar = make(qtbot, ProportionBar(LIGHT, [Segment("#0f0", 1), Segment("#f00", 1)]), (200, 10))

    bar.set_segments([Segment("#0f0", 3), Segment("#f00", 1)])

    assert bar._shares(0.5) == [0.625, 0.375]


def test_animated_money_label_counts_to_the_new_amount(qtbot, animations):
    label = AnimatedMoneyLabel(ars("100"))
    qtbot.addWidget(label)

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


def test_proportion_bar_parts_follow_their_key(qtbot):
    """A part that leaves must not hand its width to the next one."""
    bar = make(
        qtbot,
        ProportionBar(LIGHT, [Segment("#0f0", 1, "ars"), Segment("#00f", 1, "eur"),
                              Segment("#f00", 2, "usd")]),
        (200, 10),
    )  # fmt: skip

    bar.set_segments([Segment("#0f0", 1, "ars"), Segment("#f00", 1, "usd")])

    assert bar._shares(0) == [0.25, 0.5]


@pytest.mark.parametrize(
    ("cents", "currency", "text"),
    [
        (293_827_885, Currency.ARS, "$2.9M"),
        (1_500_000, Currency.USD, "US$15K"),
        (95_000, Currency.ARS, "$950"),
        (-120_000_000, Currency.ARS, "-$1.2M"),
    ],
)
def test_format_compact_in_english(english, cents, currency, text):
    assert format_compact(cents, currency) == text


def test_format_change_in_english(english):
    assert format_change(-0.095) == "↘ 9.5%"
    assert format_change(-0.05, "pp") == "↘ 5 pp"


def test_a_repeated_color_turns_into_a_shade_of_it():
    """A subcategory often keeps its category's color; in one chart they must differ."""
    colors = distinct_colors(["#e67e22", "#2980b9", "#E67E22", "#e67e22"])

    assert colors[:2] == ["#e67e22", "#2980b9"]
    assert len(set(colors)) == 4


@pytest.mark.parametrize(
    ("span", "step"), [(0.7, 1), (1.3, 2), (2.2, 2.5), (3, 5), (7, 10), (1_470_000, 2_000_000)]
)
def test_a_step_is_1_2_25_or_5_times_a_power_of_ten(span, step):
    assert nice_step(span) == step


def test_the_guides_of_a_bar_chart_are_round_and_cover_its_bars():
    """About three round steps from zero past the highest bar, and below zero for a
    negative stack."""
    assert value_axis(0, 1_470_000) == [0, 500_000, 1_000_000, 1_500_000]
    assert value_axis(-300, 900) == [-500, 0, 500, 1000]
    assert value_axis(0, 0) == [0]
