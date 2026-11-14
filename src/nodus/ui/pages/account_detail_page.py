"""The page about one account: how it is doing this month, what is coming, its balance
over time and all its movements."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from nodus.models.account import Account
from nodus.models.currency import HOME_CURRENCY, Currency
from nodus.models.money import Money
from nodus.models.period import Month
from nodus.models.recurring_charge import RecurringCharge
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.container import Services
from nodus.services.errors import NotFoundError
from nodus.ui.dialogs.account_dialog import AccountDialog
from nodus.ui.dialogs.recurring_charge_dialog import PayChargeDialog
from nodus.ui.dialogs.value_adjustment_dialog import ValueAdjustmentDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.labels import ACCOUNT_TYPE_LABELS, estimate_text
from nodus.ui.navigation import DetailId
from nodus.ui.pages.accounts_page import account_delete_warning, delete_account
from nodus.ui.pages.dashboard_cards import (
    FigureTile,
    UpcomingPaymentRow,
    card_header,
    muted_label,
)
from nodus.ui.pages.detail_page import DetailPage, danger_zone
from nodus.ui.pages.recurring_page import skip_charge
from nodus.ui.pages.transaction_list_view import TransactionListView
from nodus.ui.theme.design import Chart, Layout, Space
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.change_badge import format_signed_percent
from nodus.ui.widgets.chart_base import format_compact
from nodus.ui.widgets.figure_row import FigureRow
from nodus.ui.widgets.goal_bar import month_phrase
from nodus.ui.widgets.line_chart import LineChart, LinePoint
from nodus.ui.widgets.money_label import MoneyLabel, amount_text, masked, month_change_text
from nodus.ui.widgets.net_worth_card import signed
from nodus.ui.widgets.row_actions import MoreButton, RowAction
from nodus.ui.widgets.segmented import SegmentedControl
from nodus.ui.widgets.style import clear_layout
from nodus.ui.widgets.transaction_table import ACCOUNT

# How far back the balance chart looks: months, or None for the account's whole life.
CHART_RANGES: tuple[tuple[int | None, str], ...] = ((6, "6 meses"), (12, "1 año"), (None, "Todo"))


def chart_since(months: int | None, today: date) -> date | None:
    """The first day the chart shows: the start of the month ``months`` back, counting
    this one; None for the whole life."""
    return None if months is None else Month.of(today).shifted(1 - months).start


class AccountDetailPage(DetailPage):
    """An account at a glance: what it is and where it sits, its balance with this
    month's change, what came in and went out this month, what it gained by itself or
    still owes in installments, the goals it fills, the payments due from it, the balance
    over time and every movement, with the same menus and selection as Transacciones.

    The everyday actions are in the header; deleting, which takes the movements with it,
    is in the «Zona de peligro» at the foot.
    """

    goal_requested = Signal(int)  # goal id

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

        self.value_button = self.add_header_button("Actualizar valor")
        self.value_button.setToolTip(
            "Anota lo que vale hoy; la diferencia es rendimiento, no un ingreso"
        )
        self.value_button.clicked.connect(self.update_value)
        self.edit_button = self.add_header_button("Editar")
        self.edit_button.clicked.connect(self.edit)
        self.more_button = MoreButton(self.more_actions)
        self.add_header_widget(self.more_button)

        # The page scrolls, so the movements keep room below everything else.
        container = QWidget()
        body = QVBoxLayout(container)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(Space.L)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        self.content_layout.addWidget(scroll)

        # What the account is, in one quiet line under its name: type, currency, group.
        self.context_label = muted_label("")
        body.addWidget(self.context_label)

        # The figures; the ones that do not apply to this account hide.
        self.figures = FigureRow()
        self.balance_label = MoneyLabel()
        self.balance_note = muted_label("")
        self.converted_label = QLabel()
        self.incoming_label, self.incoming_note = QLabel(), muted_label("")
        self.outgoing_label, self.outgoing_note = QLabel(), muted_label("")
        self.gain_label, self.gain_note = QLabel(), muted_label("")
        # What is still to come off the account in installments, as a card's statement
        # lists the installments ahead.
        self.pending_label, self.pending_note = QLabel(), muted_label("")
        self.balance_tile = FigureTile("Saldo", self.balance_label, self.balance_note, large=True)
        self.converted_tile = FigureTile("En pesos", self.converted_label, large=True)
        self.incoming_tile = FigureTile(
            "Entró este mes", self.incoming_label, self.incoming_note, large=True
        )
        self.outgoing_tile = FigureTile(
            "Salió este mes", self.outgoing_label, self.outgoing_note, large=True
        )
        self.gain_tile = FigureTile("Rendimiento", self.gain_label, self.gain_note, large=True)
        self.pending_tile = FigureTile(
            "Cuotas por pagar", self.pending_label, self.pending_note, large=True
        )
        tiles = (
            self.balance_tile, self.converted_tile, self.incoming_tile, self.outgoing_tile,
            self.gain_tile, self.pending_tile,
        )  # fmt: skip
        for tile in tiles:
            self.figures.add_tile(tile)
        body.addWidget(self.figures)

        self.goals_line = QWidget()
        self._goals_layout = QHBoxLayout(self.goals_line)
        self._goals_layout.setContentsMargins(0, 0, 0, 0)
        self._goals_layout.setSpacing(Space.S)
        body.addWidget(self.goals_line)

        # The recurring charges paid from this account, each with its «Pagar».
        self.payments_card = Card("Próximos pagos")
        self._payment_rows = QVBoxLayout()
        self._payment_rows.setSpacing(0)
        self.payments_card.body.addLayout(self._payment_rows)
        self.payment_rows: list[UpcomingPaymentRow] = []
        body.addWidget(self.payments_card)

        chart_card = Card()
        header = card_header(chart_card, "Saldo en el tiempo")
        self.range_input = SegmentedControl([label for _months, label in CHART_RANGES])
        months = services.settings.account_chart_months()
        self.range_input.set_index(
            next(i for i, (m, _label) in enumerate(CHART_RANGES) if m == months)
        )
        self.range_input.changed.connect(self._set_chart_range)
        header.addWidget(self.range_input)
        self.chart = LineChart(
            theme_manager.theme, self._format_value, self._format_axis, self._format_day
        )
        self.chart.setFixedHeight(Chart.ACCOUNT_HEIGHT)
        chart_card.body.addWidget(self.chart)
        theme_manager.theme_changed.connect(self.chart.set_theme)
        body.addWidget(chart_card)

        self.list_view = TransactionListView(services, event_bus, theme_manager, self)
        self.list_view.empty_state.set_message("Esta cuenta todavía no tiene movimientos.")
        # Every row would repeat the account.
        self.list_view.table.setColumnHidden(ACCOUNT, True)
        self.list_view.setMinimumHeight(Layout.DETAIL_LIST_MIN_HEIGHT)
        body.addWidget(self.list_view, stretch=1)

        self.danger_card, self.delete_button = danger_zone("", "Eliminar cuenta", self.delete)
        self._danger_text = self.danger_card.findChild(QLabel, "FieldHint")
        body.addWidget(self.danger_card)

        for signal in (
            event_bus.accounts_changed,
            event_bus.transactions_changed,
            event_bus.exchange_rates_changed,
            event_bus.categories_changed,
            event_bus.payees_changed,
            event_bus.tags_changed,
            event_bus.goals_changed,
            event_bus.recurring_changed,
        ):
            signal.connect(self._data_changed)
        event_bus.amounts_hidden_changed.connect(self._set_amounts_hidden)

    def refresh(self) -> None:
        if self.item_id is None:
            return
        try:
            account = self.account = self._services.accounts.get(self.item_id)
        except NotFoundError:
            self.back_requested.emit()
            return
        today = self.today or date.today()
        self.title_label.setText(account.name)
        self.context_label.setText(self._context(account))
        self.value_button.setVisible(account.type.changes_value and not account.is_archived)
        self._show_figures(account, today)
        self._show_goals(account)
        self._show_payments(account, today)
        self._show_chart(account, today)
        self.list_view.show_matching(TransactionFilter(account_id=account.id))
        self._danger_text.setText(account_delete_warning(self._services, account))

    def more_actions(self) -> list[RowAction]:
        account = self.account
        if account is None:
            return []
        return [
            RowAction(
                "Desarchivar" if account.is_archived else "Archivar",
                self.toggle_archived,
                "archive",
            )
        ]

    def edit(self) -> None:
        AccountDialog(self._services, self._event_bus, self.account, parent=self.window()).exec()

    def update_value(self) -> None:
        ValueAdjustmentDialog(
            self._services, self._event_bus, self.account, parent=self.window()
        ).exec()

    def toggle_archived(self) -> None:
        self._services.accounts.set_archived(self.account.id, not self.account.is_archived)
        self._event_bus.accounts_changed.emit()

    def delete(self) -> None:
        if delete_account(self.window(), self._services, self._event_bus, self.account):
            self.back_requested.emit()

    def pay(self, charge: RecurringCharge) -> None:
        PayChargeDialog(self._services, self._event_bus, charge, parent=self.window()).exec()

    # Building

    def _context(self, account: Account) -> str:
        """ "Inversión · ARS · Ahorro e inversiones · Archivada"."""
        details = [ACCOUNT_TYPE_LABELS[account.type], account.currency.value]
        if account.group_id is not None:
            details.append(self._services.account_groups.get(account.group_id).name)
        if account.is_archived:
            details.append("Archivada")
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
        self.incoming_note.setText(self._transfers_note(activity.transfers_in, "de"))
        self.outgoing_label.setText(amount_text(activity.outgoing, hidden))
        self.outgoing_note.setText(self._transfers_note(activity.transfers_out, "a"))

        gain = accounts.value_change(account.id) if account.type.changes_value else None
        self.gain_tile.setVisible(gain is not None)
        if gain is not None:
            self.gain_label.setText(masked(gain) if hidden else signed(gain))
            invested = balance - gain
            self.gain_note.setText(
                f"{format_signed_percent(gain.cents / invested.cents)} sobre lo invertido"
                if invested.cents > 0 and not gain.is_zero
                else ""
            )

        installments = self._services.installments
        pending = installments.pending_for_account(account.id, today)
        self.pending_tile.setVisible(pending is not None)
        if pending is not None:
            self.pending_label.setText(amount_text(pending, hidden))
            left, last = installments.installments_left(account.id, today)
            count = "1 cuota" if left == 1 else f"{left} cuotas"
            self.pending_note.setText(f"{count} · hasta {month_phrase(Month.of(last))}")
        self.figures.relayout()

    def _transfers_note(self, transfers: Money, preposition: str) -> str:
        """ "US$ 100,00 de otras cuentas" / "… a otras cuentas": how much of the month's
        money in or out was only moved between the user's accounts."""
        if transfers.is_zero:
            return ""
        return f"{amount_text(transfers, self._hidden)} {preposition} otras cuentas"

    def _show_converted(self, balance: Money, today: date) -> None:
        """A foreign balance also in pesos, at today's rate, as the net worth counts it."""
        if balance.currency is HOME_CURRENCY:
            self.converted_tile.hide()
            return
        converted = self._services.exchange_rates.convert(balance, HOME_CURRENCY, today)
        if converted is None:
            self.converted_label.setText("—")
            self.converted_label.setToolTip("Sin cotización para pasarlo a pesos")
        else:
            self.converted_label.setText(f"≈ {amount_text(converted, self._hidden)}")
            self.converted_label.setToolTip(
                "Con la cotización de hoy, como lo cuenta el patrimonio"
            )
        self.converted_tile.show()

    def _show_goals(self, account: Account) -> None:
        """ "Aporta a: Vacaciones (100 %)", each goal a link to its page; nothing when
        the account fills no goal, so spending from it is not a surprise to the goal."""
        clear_layout(self._goals_layout)
        goals = self._services.goals.goals_for_account(account.id)
        self.goals_line.setVisible(bool(goals))
        if not goals:
            return
        self._goals_layout.addWidget(muted_label("Aporta a:"))
        for goal, percent in goals:
            link = QPushButton(f"{goal.name} ({percent} %)")
            link.setObjectName("LinkButton")
            link.setCursor(Qt.CursorShape.PointingHandCursor)
            link.setToolTip("Abrir la meta")
            link.clicked.connect(lambda _=False, i=goal.id: self.goal_requested.emit(i))
            self._goals_layout.addWidget(link)
        self._goals_layout.addStretch()

    def _show_payments(self, account: Account, today: date) -> None:
        """The account's active recurring charges, the soonest first; no card without."""
        clear_layout(self._payment_rows)
        recurring = self._services.recurring
        charges = [
            c for c in recurring.list_charges() if c.is_active and c.account_id == account.id
        ]
        self.payments_card.setVisible(bool(charges))
        self.payment_rows = []
        for charge in charges:
            estimate = recurring.estimated_payment(charge, today)
            row = UpcomingPaymentRow(charge, today, estimate_text(charge.amount, estimate))
            row.pay_requested.connect(self.pay)
            row.skip_requested.connect(lambda c: skip_charge(self._services, self._event_bus, c))
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

    def _data_changed(self) -> None:
        # Hidden, it is refreshed when shown again.
        if self.isVisible():
            self.refresh()

    def _set_amounts_hidden(self, hidden: bool) -> None:
        self._hidden = hidden
        self._data_changed()

    def _currency(self) -> Currency:
        return self.account.currency if self.account else HOME_CURRENCY

    def _format_value(self, cents: float) -> str:
        return amount_text(Money(round(cents), self._currency()), self._hidden)

    def _format_axis(self, cents: float) -> str:
        return "" if self._hidden else format_compact(cents, self._currency())

    def _format_day(self, day: date) -> str:
        return f"{day:%d/%m}" if self._daily else Month.of(day).short_name
