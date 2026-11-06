"""Card with the user's net worth in pesos and dollars."""

from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import QGridLayout, QLabel

from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.services.container import Services
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.stat import Stat
from nodus.ui.widgets.style import set_style_property


class NetWorthCard(Card):
    """Totals converted to each currency, what is held in each, and the rate used.

    Shown on the dashboard and on the accounts page, always as of ``day``.
    """

    def __init__(self, services: Services, day: date, title: str | None = None) -> None:
        super().__init__(title)
        net_worth = services.net_worth.net_worth(day)
        # Totals on top, what each currency holds below, one currency per column.
        stats = QGridLayout()
        stats.setHorizontalSpacing(40)
        stats.setVerticalSpacing(12)
        for column, (currency, name) in enumerate(
            [(Currency.ARS, "pesos"), (Currency.USD, "dólares")]
        ):
            stats.addWidget(
                Stat(f"Patrimonio en {name}", net_worth.total_in[currency], large=True), 0, column
            )
            stats.addWidget(
                Stat(f"En cuentas en {name}", net_worth.by_currency[currency]), 1, column
            )
        stats.setColumnStretch(2, 1)
        self.body.addLayout(stats)
        note = QLabel(self._rate_note(services, day))
        note.setWordWrap(True)
        set_style_property(note, "muted", True)
        self.body.addWidget(note)

    @staticmethod
    def _rate_note(services: Services, day: date) -> str:
        rate = services.exchange_rates.rate_on(day)
        if rate is None:
            return "Sin cotización: cárgala en Ajustes"
        value = Money.from_decimal(rate.rate, Currency.ARS).format()
        return f"US$ 1 = {value} · {rate.rate_date:%d/%m}"
