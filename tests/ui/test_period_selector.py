from datetime import date

from PySide6.QtCore import Qt

from nodus.models.period import Month, Period, QuickPeriod
from nodus.ui.dialogs.date_range_dialog import DateRangeDialog
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
    assert texts == [quick.value for quick in QuickPeriod] + ["", "Personalizado…"]

    selector.quick_menu.actions()[4].trigger()  # Este año

    assert selector.period() == Period.year(date.today().year)
    assert selector.period_button.text() == str(date.today().year)


def test_custom_range_is_labelled_and_moves_by_its_length(monkeypatch, qtbot):
    chosen = Period(date(2026, 10, 3), date(2026, 11, 15))

    def fake_exec(dialog):
        assert dialog.period == NOVEMBER  # starts on the period shown
        dialog.period = chosen
        return True

    monkeypatch.setattr(DateRangeDialog, "exec", fake_exec)
    selector = make_selector(qtbot)

    selector.quick_menu.actions()[-1].trigger()

    assert selector.period() == chosen
    assert selector.period_button.text() == "03/10/2026 – 15/11/2026"
    selector.next_button.click()
    assert selector.period() == Period(date(2026, 11, 16), date(2026, 12, 29))


def test_range_dialog_rejects_an_end_before_the_start(qtbot):
    dialog = DateRangeDialog(NOVEMBER)
    qtbot.addWidget(dialog)
    dialog.start_input.set_day(date(2026, 11, 20))
    dialog.end_input.set_day(date(2026, 11, 10))

    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

    assert "anterior" in dialog.field_error(dialog.end_input)
    assert dialog.period == NOVEMBER
    dialog.end_input.set_day(date(2026, 11, 25))
    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
    assert dialog.period == Period(date(2026, 11, 20), date(2026, 11, 25))


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
