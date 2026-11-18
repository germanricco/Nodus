"""Inicio: the recurring charges due soon."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout

from nodus.i18n import _, ngettext
from nodus.services.container import Services
from nodus.services.transactions.recurring_charge_service import UPCOMING_DAYS
from nodus.ui.text.labels import estimate_text
from nodus.ui.widgets.card import Card, card_header, see_all_link
from nodus.ui.widgets.style import clear_layout, muted_label
from nodus.ui.widgets.tables.charge_row import UpcomingPaymentRow

# Upcoming charges listed on the dashboard; the page has them all.
UPCOMING_COUNT = 3


class UpcomingPaymentsCard(Card):
    """Recurring charges overdue or due in the next days, each with a quick "Pagar"."""

    pay_requested = Signal(object)  # RecurringCharge
    skip_requested = Signal(object)  # RecurringCharge
    seen_toggled = Signal(object)  # RecurringCharge
    see_all_requested = Signal()

    def __init__(self, services: Services) -> None:
        super().__init__()
        self._services = services
        header = card_header(self, _("Próximos pagos"))
        self.monthly_label = muted_label("")
        self.monthly_label.setToolTip(_("Lo que suman tus cargos recurrentes en un mes"))
        header.addWidget(self.monthly_label)
        self.see_all_button = see_all_link(header, _("Ver todos"), self.see_all_requested)
        self._rows = QVBoxLayout()
        self._rows.setSpacing(0)
        self.body.addLayout(self._rows)
        # Extra height goes below the rows, keeping the title on top.
        self.body.addStretch()
        self.rows: list[UpcomingPaymentRow] = []

    def show_data(self, today: date) -> None:
        """Hides the card when there are no active charges."""
        recurring = self._services.recurring
        summary = recurring.summary(today)
        self.setVisible(summary.active > 0)
        self.monthly_label.setText(_("~{amount}/mes").format(amount=summary.monthly.format()))
        clear_layout(self._rows)
        charges = recurring.upcoming(today)
        self.rows = []
        if not charges:
            nothing_due = ngettext(
                "Nada que pagar en el próximo {count} día",
                "Nada que pagar en los próximos {count} días",
                UPCOMING_DAYS,
            ).format(count=UPCOMING_DAYS)
            self._rows.addWidget(muted_label(nothing_due))
        for charge in charges[:UPCOMING_COUNT]:
            estimate = self._services.recurring.estimated_payment(charge, today)
            row = UpcomingPaymentRow(
                charge,
                today,
                recurring.is_quiet(charge, today),
                estimate_text(charge.amount, estimate),
            )
            row.pay_requested.connect(self.pay_requested)
            row.skip_requested.connect(self.skip_requested)
            row.seen_toggled.connect(self.seen_toggled)
            self._rows.addWidget(row)
            self.rows.append(row)
