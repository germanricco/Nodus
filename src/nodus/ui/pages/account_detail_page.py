"""The page about one account: its balance over time and all its movements."""

from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import QHBoxLayout, QLabel

from nodus.models.account import Account
from nodus.models.currency import HOME_CURRENCY, Currency
from nodus.models.money import Money
from nodus.models.period import Month
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.container import Services
from nodus.services.errors import NotFoundError
from nodus.ui.dialogs.account_dialog import AccountDialog
from nodus.ui.dialogs.value_adjustment_dialog import ValueAdjustmentDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.labels import ACCOUNT_TYPE_LABELS
from nodus.ui.navigation import DetailId
from nodus.ui.pages.accounts_page import account_delete_warning, delete_account
from nodus.ui.pages.dashboard_cards import FigureTile
from nodus.ui.pages.detail_page import DetailPage, danger_zone
from nodus.ui.pages.transaction_list_view import TransactionListView
from nodus.ui.theme.design import Chart, Space
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.chart_base import format_compact
from nodus.ui.widgets.line_chart import LineChart, LinePoint
from nodus.ui.widgets.money_label import MoneyLabel, masked
from nodus.ui.widgets.net_worth_card import signed
from nodus.ui.widgets.row_actions import MoreButton, RowAction
from nodus.ui.widgets.transaction_table import ACCOUNT

# Tall enough to read the trend, short enough to leave the movements most of the page.


class AccountDetailPage(DetailPage):
    """An account at a glance: its balance (in pesos too, for a foreign currency), what it
    gained by itself, the balance over its whole life and every movement, with the same
    menus and selection as Transacciones.

    The everyday actions are in the header; deleting, which takes the movements with it,
    is in the «Zona de peligro» at the foot.
    """

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__(DetailId.ACCOUNT, theme_manager)
        self._services = services
        self._event_bus = event_bus
        self.account: Account | None = None
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

        # The figures in a row, as on the pages of a payee or a tag; the ones that do not
        # apply to this account (pesos, return) hide.
        figures = QHBoxLayout()
        figures.setSpacing(Space.M)
        self.balance_label = MoneyLabel()
        self.converted_label = QLabel()
        self.gain_label = QLabel()
        self.pending_label = QLabel()
        self.kind_label = QLabel()
        self.balance_tile = FigureTile("Saldo", self.balance_label, large=True)
        self.converted_tile = FigureTile("En pesos", self.converted_label, large=True)
        self.gain_tile = FigureTile("Rendimiento", self.gain_label, large=True)
        # What is still to come off the account in installments, as a card's statement
        # lists the installments ahead.
        self.pending_tile = FigureTile("Cuotas por pagar", self.pending_label, large=True)
        self.kind_tile = FigureTile("Tipo", self.kind_label, large=True)
        tiles = (
            self.balance_tile, self.converted_tile, self.gain_tile, self.pending_tile,
            self.kind_tile,
        )  # fmt: skip
        for tile in tiles:
            figures.addWidget(tile, stretch=1)
        self.content_layout.addLayout(figures)
        chart_card = Card("Saldo en el tiempo")
        self.chart = LineChart(
            theme_manager.theme, self._format_value, self._format_axis, self._format_day
        )
        self.chart.setFixedHeight(Chart.ACCOUNT_HEIGHT)
        chart_card.body.addWidget(self.chart)
        theme_manager.theme_changed.connect(self.chart.set_theme)
        self.content_layout.addWidget(chart_card)

        self.list_view = TransactionListView(services, event_bus, theme_manager, self)
        self.list_view.empty_state.set_message("Esta cuenta todavía no tiene movimientos.")
        # Every row would repeat the account.
        self.list_view.table.setColumnHidden(ACCOUNT, True)
        self.content_layout.addWidget(self.list_view, stretch=1)

        self.danger_card, self.delete_button = danger_zone("", "Eliminar cuenta", self.delete)
        self._danger_text = self.danger_card.findChild(QLabel, "FieldHint")
        self.content_layout.addWidget(self.danger_card)

        for signal in (
            event_bus.accounts_changed,
            event_bus.transactions_changed,
            event_bus.exchange_rates_changed,
            event_bus.categories_changed,
            event_bus.payees_changed,
            event_bus.tags_changed,
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
        today = date.today()
        self.title_label.setText(account.name)
        details = [ACCOUNT_TYPE_LABELS[account.type], account.currency.value]
        if account.is_archived:
            details.append("Archivada")
        self.kind_label.setText(" · ".join(details))
        balance = self._services.accounts.balance(account.id)
        self.balance_label.set_hidden(self._hidden)
        self.balance_label.set_money(balance)
        self._show_converted(balance, today)
        gain = (
            self._services.accounts.value_change(account.id) if account.type.changes_value else None
        )
        self.gain_tile.setVisible(gain is not None)
        if gain is not None:
            self.gain_label.setText(masked(gain) if self._hidden else signed(gain))
        self.value_button.setVisible(account.type.changes_value and not account.is_archived)
        pending = self._services.installments.pending_for_account(account.id, today)
        self.pending_tile.setVisible(pending is not None)
        if pending is not None:
            self.pending_label.setText(masked(pending) if self._hidden else pending.format())

        history = self._services.net_worth.account_history(account.id, today)
        self._daily = len(history) < 2 or (history[1][0] - history[0][0]).days == 1
        self.chart.set_points([LinePoint(day, money.cents) for day, money in history])

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
            shown = masked(converted) if self._hidden else converted.format()
            self.converted_label.setText(f"≈ {shown}")
            self.converted_label.setToolTip(
                "Con la cotización de hoy, como lo cuenta el patrimonio"
            )
        self.converted_tile.show()

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
        money = Money(round(cents), self._currency())
        return masked(money) if self._hidden else money.format()

    def _format_axis(self, cents: float) -> str:
        return "" if self._hidden else format_compact(cents, self._currency())

    def _format_day(self, day: date) -> str:
        return f"{day:%d/%m}" if self._daily else Month.of(day).short_name
