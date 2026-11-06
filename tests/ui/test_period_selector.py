from datetime import date

from nodus.models.period import Month, Period, QuickPeriod
from nodus.ui.pages.transactions_page import export_filename
from nodus.ui.widgets.period_selector import PeriodSelector

NOVEMBER = Period.of_months(Month(2026, 11))


def make_selector(qtbot, period=NOVEMBER) -> PeriodSelector:
    selector = PeriodSelector(period)
    qtbot.addWidget(selector)
    return selector


def test_starts_on_current_month(qtbot):
    selector = PeriodSelector()
    qtbot.addWidget(selector)

    assert selector.period() == Period.of_months(Month.of(date.today()))


def test_arrows_move_by_the_period_length(qtbot):
    selector = make_selector(qtbot, Period.of_months(Month(2026, 9), Month(2026, 11)))

    with qtbot.waitSignal(selector.period_changed):
        selector.previous_button.click()

    assert selector.period() == Period.of_months(Month(2026, 6), Month(2026, 8))
    assert selector.period_button.text() == "Jun – Ago 2026"


def test_quick_menu_lists_every_choice_and_applies_it(qtbot):
    selector = make_selector(qtbot)
    texts = [action.text() for action in selector.quick_menu.actions()]
    assert texts == [quick.value for quick in QuickPeriod]

    selector.quick_menu.actions()[4].trigger()  # Este año

    assert selector.period() == Period.year(date.today().year)
    assert selector.period_button.text() == str(date.today().year)


def test_setting_the_same_period_emits_nothing(qtbot):
    selector = make_selector(qtbot)

    with qtbot.assertNotEmitted(selector.period_changed):
        selector.set_period(NOVEMBER)


def test_export_filename_names_months_and_ranges():
    assert export_filename(NOVEMBER) == "nodus-transacciones-2026-11.csv"
    assert (
        export_filename(Period.of_months(Month(2026, 9), Month(2026, 11)))
        == "nodus-transacciones-2026-09-01_2026-11-30.csv"
    )
