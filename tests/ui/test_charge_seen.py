"""«Ya lo vi» on a charge due soon: the pill goes gray until the day before, and
«Volver a avisarme» brings it back."""

from datetime import date, timedelta

from factories import ars, charge_draft
from menus import run_action, texts
from PySide6.QtWidgets import QLabel

from nodus.models.period import format_date
from nodus.ui.navigation import PageId


def toast_texts(window) -> list[str]:
    return [toast.text for toast in window.toasts.toasts]


def due_in(services, pesos, days: int, name: str = "Netflix"):
    return services.recurring.create(
        charge_draft(
            services, pesos.id, ars("8500"), date.today() + timedelta(days=days), name=name
        )
    )


def tone(row) -> tuple[str, str]:
    """The tone and tooltip of the row's due pill."""
    badge = next(label for label in row.findChildren(QLabel) if label.objectName() == "ChangeBadge")
    return badge.property("tone"), badge.toolTip()


def test_ya_lo_vi_on_inicio_grays_the_pill_and_says_when(services, window, pesos):
    charge = due_in(services, pesos, 5)
    window.show_page(PageId.DASHBOARD)
    card = window.page(PageId.DASHBOARD).upcoming_card
    assert tone(card.rows[0])[0] == "warning"

    run_action(card.rows[0].actions(), "Ya lo vi")

    day = date.today() + timedelta(days=4)
    assert toast_texts(window) == [f"Te recordamos Netflix el {format_date(day)}."]
    assert tone(card.rows[0]) == (
        "neutral",
        f"Ya lo viste. Te lo recordamos el {format_date(day)}.",
    )
    assert services.recurring.get(charge.id).remind_from == day


def test_volver_a_avisarme_brings_the_warning_back(services, window, pesos):
    charge = due_in(services, pesos, 5)
    services.recurring.mark_seen(charge.id, date.today())
    window.show_page(PageId.RECURRING)
    page = window.page(PageId.RECURRING)

    run_action(page.rows[0].actions(), "Volver a avisarme")

    assert services.recurring.get(charge.id).remind_from is None
    assert tone(page.rows[0])[0] == "warning"
    assert toast_texts(window) == ["Te volvemos a avisar de Netflix."]


def test_overdue_or_due_tomorrow_offer_no_ya_lo_vi(services, window, pesos):
    due_in(services, pesos, -1, "Internet")
    due_in(services, pesos, 1, "Luz")
    window.show_page(PageId.RECURRING)

    for row in window.page(PageId.RECURRING).rows:
        assert "Ya lo vi" not in texts(row.actions())


def test_a_warning_back_tomorrow_says_so(services, window, pesos):
    due_in(services, pesos, 2)
    window.show_page(PageId.RECURRING)

    run_action(window.page(PageId.RECURRING).rows[0].actions(), "Ya lo vi")

    assert toast_texts(window) == ["Te recordamos Netflix mañana."]
