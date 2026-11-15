"""Toasts tell what just happened at the bottom right of the page and go away alone."""

from decimal import Decimal

from PySide6.QtCore import QEvent, QPointF
from PySide6.QtGui import QEnterEvent

from nodus.models.currency import Currency
from nodus.ui import main_window as main_window_module
from nodus.ui.rate_updater import updated_text
from nodus.ui.theme.design import Dwell
from nodus.ui.widgets.toast import MAX_TOASTS, show_toast


def texts(window) -> list[str]:
    return [toast.text for toast in window.toasts.toasts]


def test_it_shows_at_the_bottom_right_of_the_page(window):
    window.toast("Copia guardada.")

    stack = window.toasts
    area = stack.parentWidget().rect()
    assert stack.isVisible()
    assert texts(window) == ["Copia guardada."]
    assert stack.geometry().right() < area.right()
    assert stack.geometry().bottom() < area.bottom()
    assert stack.geometry().top() > area.center().y()


def test_each_new_toast_gets_its_whole_height(window):
    window.toast("Copia guardada.")
    one = window.toasts.height()

    window.toast("Se omitió Internet.", "Deshacer", lambda: None)

    first, second = window.toasts.toasts
    assert first.label.height() > 0 and second.label.height() > 0
    assert window.toasts.height() > 2 * first.height() > one


def test_it_keeps_the_newest_few_and_one_text_once(window):
    for number in range(MAX_TOASTS + 1):
        window.toast(f"Aviso {number}")
    window.toast("Aviso 2")

    assert texts(window) == ["Aviso 1", "Aviso 3", "Aviso 2"]


def test_the_cross_closes_it(window):
    window.toast("Copia guardada.")

    window.toasts.toasts[0].close_button.click()

    assert texts(window) == []
    assert not window.toasts.isVisible()


def test_it_goes_away_alone_but_waits_under_the_mouse(qtbot, monkeypatch, window):
    monkeypatch.setattr(Dwell, "TOAST", 50)
    window.toast("Copia guardada.")
    toast = window.toasts.toasts[0]

    toast.enterEvent(QEnterEvent(QPointF(), QPointF(), QPointF()))
    assert not toast.waiting
    toast.leaveEvent(QEvent(QEvent.Type.Leave))
    assert toast.waiting

    qtbot.waitUntil(lambda: texts(window) == [], timeout=2000)


def test_an_action_closes_it_and_runs(window):
    done = []
    window.toast("Se omitió Internet.", "Deshacer", lambda: done.append(True))
    toast = window.toasts.toasts[0]
    assert toast.action_button.text() == "Deshacer"

    toast.action_button.click()

    assert done == [True]
    assert texts(window) == []


def test_any_widget_of_the_window_can_show_one(window):
    show_toast(window.top_bar, "Cotización guardada.")

    assert texts(window) == ["Cotización guardada."]


def test_a_new_transaction_is_announced(monkeypatch, window, pesos):
    class Saved:
        def __init__(self, *_args, **_kwargs):
            pass

        def exec(self):
            return 1

    monkeypatch.setattr(main_window_module, "TransactionDialog", Saved)

    window.open_new_transaction()

    assert texts(window) == ["Transacción guardada."]


def test_new_rates_are_announced_by_the_dollar():
    rates = {Currency.USD: Decimal("1215.50"), Currency.EUR: Decimal("1410")}

    assert updated_text(rates) == "Cotización actualizada: US$ 1 = $ 1.215,50"
    assert updated_text({Currency.EUR: Decimal("1410")}) == "Cotizaciones actualizadas."
