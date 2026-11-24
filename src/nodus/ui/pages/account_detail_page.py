"""The page about one account: how it is doing this month, what is coming, its balance
over time and all its movements."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel,
)

from nodus.i18n import N_, _, ngettext
from nodus.models.account import Account
from nodus.models.currency import HOME_CURRENCY, Currency
from nodus.models.language_format import format_percent
from nodus.models.money import Money
from nodus.models.period import Month, format_month_in_sentence
from nodus.models.recurring_charge import RecurringCharge
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.container import Services
from nodus.services.errors import NotFoundError
from nodus.ui.actions.accounts import (
    delete_account,
    edit_account,
    toggle_account_archived,
)
from nodus.ui.actions.recurring import pay_charge, skip_charge, toggle_seen
from nodus.ui.dialogs.transaction_dialog import TransactionStart
from nodus.ui.dialogs.value_adjustment_dialog import ValueAdjustmentDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import DetailId, RecordLink
from nodus.ui.pages.base.detail_page import DetailPage
from nodus.ui.pages.base.transaction_list_view import TransactionListView
from nodus.ui.text.formatting import masked, signed
from nodus.ui.text.labels import ACCOUNT_TYPE_LABELS, estimate_text
from nodus.ui.theme.design import Chart, Layout
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card, card_header
from nodus.ui.widgets.change_badge import format_signed_percent
from nodus.ui.widgets.charts.line_chart import LineChart, LinePoint, money_formats
from nodus.ui.widgets.figure_row import FigureRow
from nodus.ui.widgets.figure_tile import FigureTile
from nodus.ui.widgets.hero_figure import HeroFigure
from nodus.ui.widgets.inputs.segmented import SegmentedControl
from nodus.ui.widgets.link_line import Link, LinkLine
from nodus.ui.widgets.money_label import MoneyLabel, amount_text, month_change_text
from nodus.ui.widgets.style import clear_layout, muted_label
from nodus.ui.widgets.tables.charge_row import UpcomingPaymentRow
from nodus.ui.widgets.tables.row_actions import Effect, MoreButton, RowAction
from nodus.ui.widgets.tables.row_layout import row_list
from nodus.ui.widgets.tables.transaction_table import Omit

# How far back the balance chart looks: months, or None for the account's whole life.
CHART_RANGES: tuple[tuple[int | None, str], ...] = (
    (6, N_("6 meses")),
    (12, N_("1 año")),
    (None, N_("Todo")),
)


def chart_since(months: int | None, today: date) -> date | None:
    """The first day the chart shows: the start of the month ``months`` back, counting
    this one; None for the whole life."""
    return None if months is None else Month.of(today).shifted(1 - months).start


class AccountDetailPage(DetailPage):
    """An account at a glance: what it is and where it sits, its balance with this
    month's change, what came in and went out this month, what it gained by itself or
    still owes in installments, the goals it fills, the payments due from it, the balance
    over time and every movement, with the same menus and selection as Transacciones.

    The actions are in the header; archiving and deleting, the rare ones, in its «⋯».
    """

    record_requested = Signal(object)  # RecordLink

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__(DetailId.ACCOUNT, theme_manager)
        self._services = services
        self._event_bus = event_bus
        self.account: Account | None = None
        self.today: date | None = None  # fixed by tests; otherwise the real date
        self._hidden = services.settings.amounts_hidden()
        self._daily = True
        self._add_header_buttons()

        # The page scrolls, so the movements keep room below everything else.
        body = self.scrolling_body()
        # What the account is, in one quiet line under its name: type, currency, group.
        self.context_label = muted_label("")
        body.addWidget(self.context_label)
        self.balance_label = MoneyLabel()
        self.balance_note = muted_label("")
        self.balance_figure = HeroFigure(_("Saldo"), self.balance_label, self.balance_note)
        body.addWidget(self.balance_figure)
        body.addWidget(self._figures())
        self.goals_line = LinkLine()
        body.addWidget(self.goals_line)
        body.addWidget(self._payments_card())
        body.addWidget(self._chart_card(services, theme_manager))

        # Every row would repeat the account.
        self.list_view = TransactionListView(services, event_bus, theme_manager, self, Omit.ACCOUNT)
        self.list_view.record_requested.connect(self.record_requested)
        self.list_view.add_to_page(body, Layout.DETAIL_LIST_MIN_HEIGHT)

        event_bus.amounts_hidden_changed.connect(self._set_amounts_hidden)

    def _add_header_buttons(self) -> None:
        self.value_button = self.add_header_button(_("Actualizar valor"))
        self.value_button.setToolTip(
            _("Anota lo que vale hoy; la diferencia es rendimiento, no un ingreso")
        )
        self.value_button.clicked.connect(self.update_value)
        self.edit_button = self.add_header_button(_("Editar"))
        self.edit_button.clicked.connect(self.edit)
        self.more_button = MoreButton(self.more_actions)
        self.add_header_widget(self.more_button)

    def _figures(self) -> FigureRow:
        """The figures under the balance; the ones that do not apply to this account hide."""
        self.figures = FigureRow()
        self.converted_label = QLabel()
        self.incoming_label, self.incoming_note = QLabel(), muted_label("")
        self.outgoing_label, self.outgoing_note = QLabel(), muted_label("")
        self.gain_label, self.gain_note = QLabel(), muted_label("")
        # What is still to come off the account in installments, as a card's statement
        # lists the installments ahead.
        self.pending_label, self.pending_note = QLabel(), muted_label("")
        self.converted_tile = FigureTile(_("En pesos"), self.converted_label)
        self.incoming_tile = FigureTile(
            _("Entró este mes"), self.incoming_label, self.incoming_note
        )
        self.outgoing_tile = FigureTile(
            _("Salió este mes"), self.outgoing_label, self.outgoing_note
        )
        self.gain_tile = FigureTile(_("Rendimiento"), self.gain_label, self.gain_note)
        self.pending_tile = FigureTile(_("Cuotas por pagar"), self.pending_label, self.pending_note)
        tiles = (
            self.converted_tile, self.incoming_tile, self.outgoing_tile, self.gain_tile,
            self.pending_tile,
        )  # fmt: skip
        for tile in tiles:
            self.figures.add_tile(tile)
        return self.figures

    def _payments_card(self) -> Card:
        """The recurring charges paid from this account, each with its «Pagar»."""
        self.payments_card = Card(_("Próximos pagos"))
        self._payment_rows = row_list()
        self.payments_card.body.addLayout(self._payment_rows)
        self.payment_rows: list[UpcomingPaymentRow] = []
        return self.payments_card

    def _chart_card(self, services: Services, theme_manager: ThemeManager) -> Card:
        chart_card = Card()
        header = card_header(chart_card, _("Saldo en el tiempo"))
        self.range_input = SegmentedControl([_(label) for _months, label in CHART_RANGES])
        months = services.settings.account_chart_months()
        self.range_input.set_index(
            next(i for i, (m, _label) in enumerate(CHART_RANGES) if m == months)
        )
        self.range_input.changed.connect(self._set_chart_range)
        header.addWidget(self.range_input)
        self.chart = LineChart(
            theme_manager.theme,
            *money_formats(self._currency, lambda: self._hidden, lambda: self._daily),
        )
        self.chart.setFixedHeight(Chart.DETAIL_HEIGHT)
        chart_card.body.addWidget(self.chart)
        theme_manager.theme_changed.connect(self.chart.set_theme)
        return chart_card

    def refresh(self) -> None:
        if self.item_id is None:
            return
        try:
            account = self.account = self._services.accounts.get(self.item_id)
        except NotFoundError:
            self.back_requested.emit()
            return
        today = self.today or date.today()
        self.set_title(account.name)
        self.context_label.setText(self._context(account))
        self.value_button.setVisible(account.type.changes_value and not account.is_archived)
        self._show_figures(account, today)
        self._show_goals(account)
        self._show_payments(account, today)
        self._show_chart(account, today)
        self.list_view.show_matching(TransactionFilter(account_id=account.id))
        self._set_empty_message(account)

    def _set_empty_message(self, account: Account) -> None:
        """An active account offers its first movement; an archived one takes none."""
        text = _("Esta cuenta todavía no tiene movimientos.")
        if account.is_archived:
            self.list_view.empty_state.set_message(text)
            return
        start = TransactionStart(account_id=account.id)
        self.list_view.empty_state.set_message(
            text, _("Agregar transacción"), lambda: self.new_transaction_requested.emit(start)
        )

    def more_actions(self) -> list[RowAction]:
        account = self.account
        if account is None:
            return []
        return [
            RowAction(
                _("Desarchivar") if account.is_archived else _("Archivar"),
                self.toggle_archived,
                "archive",
                effect=Effect.TOGGLE,
            ),
            RowAction(
                _("Eliminar"), self.delete, "trash", destructive=True, effect=Effect.CONFIRMED
            ),
        ]

    def edit(self) -> None:
        edit_account(self, self._services, self._event_bus, self.account)

    def update_value(self) -> None:
        ValueAdjustmentDialog(
            self._services, self._event_bus, self.account, parent=self.window()
        ).exec()

    def toggle_archived(self) -> None:
        toggle_account_archived(self._services, self._event_bus, self.account)

    def delete(self) -> None:
        if delete_account(self.window(), self._services, self._event_bus, self.account):
            self.back_requested.emit()

    def pay(self, charge: RecurringCharge) -> None:
        pay_charge(self, self._services, self._event_bus, charge)

    # Building

    def _context(self, account: Account) -> str:
        """ "Inversión · ARS · Ahorro e inversiones · Archivada"."""
        details = [_(ACCOUNT_TYPE_LABELS[account.type]), account.currency.value]
        if account.group_id is not None:
            details.append(self._services.account_groups.get(account.group_id).name)
        if account.is_archived:
            details.append(_("Archivada"))
        return " · ".join(details)

    def _show_figures(self, account: Account, today: date) -> None:
        hidden = self._hidden
        accounts = self._services.accounts
        balance = accounts.balance(account.id, today)
        self.balance_label.set_hidden(hidden)
        self.balance_label.set_money(balance)
        month = Month.of(today)
        before = accounts.balance(account.id, month.previous().end)
        self.balance_note.setText(month_change_text(balance - before, hidden))
        self._show_converted(balance, today)

        activity = self._services.transactions.account_activity(account, month.start, today)
        self.incoming_label.setText(amount_text(activity.incoming, hidden))
        self.incoming_note.setText(
            self._transfers_note(activity.transfers_in, _("{amount} de otras cuentas"))
        )
        self.outgoing_label.setText(amount_text(activity.outgoing, hidden))
        self.outgoing_note.setText(
            self._transfers_note(activity.transfers_out, _("{amount} a otras cuentas"))
        )

        gain = accounts.value_gain(account, balance)
        self.gain_tile.setVisible(gain is not None)
        if gain is not None:
            self.gain_label.setText(masked(gain.amount) if hidden else signed(gain.amount))
            self.gain_note.setText(
                ""
                if gain.share is None
                else _("{share} sobre lo invertido").format(share=format_signed_percent(gain.share))
            )

        installments = self._services.installments
        pending = installments.pending_for_account(account.id, today)
        self.pending_tile.setVisible(pending is not None)
        if pending is not None:
            self.pending_label.setText(amount_text(pending, hidden))
            left, last = installments.installments_left(account.id, today)
            count = ngettext("{count} cuota", "{count} cuotas", left).format(count=left)
            self.pending_note.setText(
                _("{installments} · hasta {month}").format(
                    installments=count, month=format_month_in_sentence(Month.of(last))
                )
            )
        self.figures.relayout()

    def _transfers_note(self, transfers: Money, sentence: str) -> str:
        """ "US$ 100,00 de otras cuentas" / "… a otras cuentas": how much of the month's
        money in or out was only moved between the user's accounts."""
        if transfers.is_zero:
            return ""
        return sentence.format(amount=amount_text(transfers, self._hidden))

    def _show_converted(self, balance: Money, today: date) -> None:
        """A foreign balance also in pesos, at today's rate, as the net worth counts it."""
        if balance.currency is HOME_CURRENCY:
            self.converted_tile.hide()
            return
        converted = self._services.exchange_rates.convert(balance, HOME_CURRENCY, today)
        if converted is None:
            self.converted_label.setText("—")
            self.converted_label.setToolTip(_("Sin cotización para pasarlo a pesos"))
        else:
            self.converted_label.setText(f"≈ {amount_text(converted, self._hidden)}")
            self.converted_label.setToolTip(
                _("Con la cotización de hoy, como lo cuenta el patrimonio")
            )
        self.converted_tile.show()

    def _show_goals(self, account: Account) -> None:
        """ "Aporta a: Vacaciones (100 %)", each goal a link to its page; nothing when
        the account fills no goal, so spending from it is not a surprise to the goal."""
        goals = self._services.goals.goals_for_account(account.id)
        self.goals_line.set_links(
            _("Aporta a:"),
            [
                Link(
                    f"{goal.name} ({format_percent(percent)})",
                    DetailId.GOAL.open_text,
                    lambda i=goal.id: self.record_requested.emit(RecordLink.goal(i)),
                )
                for goal, percent in goals
            ],
        )

    def _show_payments(self, account: Account, today: date) -> None:
        """The account's active recurring charges, the soonest first; no card without."""
        clear_layout(self._payment_rows)
        recurring = self._services.recurring
        charges = recurring.active_for_account(account.id)
        self.payments_card.setVisible(bool(charges))
        self.payment_rows = []
        for charge in charges:
            estimate = recurring.estimated_payment(charge, today)
            row = UpcomingPaymentRow(
                charge,
                today,
                recurring.is_quiet(charge, today),
                estimate_text(charge.amount, estimate),
            )
            row.pay_requested.connect(self.pay)
            row.skip_requested.connect(
                lambda c: skip_charge(self, self._services, self._event_bus, c)
            )
            row.seen_toggled.connect(
                lambda c: toggle_seen(self, self._services, self._event_bus, c)
            )
            self._payment_rows.addWidget(row)
            self.payment_rows.append(row)

    def _show_chart(self, account: Account, today: date) -> None:
        months = CHART_RANGES[self.range_input.index()][0]
        history = self._services.net_worth.account_history(
            account.id, today, chart_since(months, today)
        )
        self._daily = len(history) < 2 or (history[1][0] - history[0][0]).days == 1
        self.chart.set_points([LinePoint(day, money.cents) for day, money in history])

    def _set_chart_range(self, index: int) -> None:
        """Saves the chosen range, the same for every account, and redraws."""
        self._services.settings.set_account_chart_months(CHART_RANGES[index][0])
        if self.account is not None:
            self._show_chart(self.account, self.today or date.today())

    def _set_amounts_hidden(self, hidden: bool) -> None:
        self._hidden = hidden
        self.request_refresh()

    def _currency(self) -> Currency:
        return self.account.currency if self.account else HOME_CURRENCY
