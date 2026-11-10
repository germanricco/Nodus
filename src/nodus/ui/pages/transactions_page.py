"""Transactions section: every movement of a month, with filters."""

from __future__ import annotations

from functools import partial

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
)

from nodus.models.period import Period
from nodus.models.transaction import TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.container import Services
from nodus.ui.dialogs.export import export_transactions
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import PageId, TransactionFocus
from nodus.ui.pages.page import Page
from nodus.ui.pages.transaction_list_view import TransactionListView
from nodus.ui.theme.design import Space
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.combo_box import ComboBox
from nodus.ui.widgets.period_selector import PeriodSelector
from nodus.ui.widgets.selectors import (
    AccountComboBox,
    CategoryComboBox,
    PayeeComboBox,
    TagComboBox,
)
from nodus.ui.widgets.style import set_style_property

# Type filter: label -> (transaction type, is_transfer, refund_linked) criteria.
TYPE_FILTERS = {
    "Tipo": (None, None, None),
    "Gastos": (TransactionType.EXPENSE, False, None),
    "Ingresos": (TransactionType.INCOME, False, None),
    "Transferencias": (None, True, None),
    "Reembolsos": (None, False, True),
}


def export_filename(period: Period) -> str:
    """ "nodus-transacciones-2026-11.csv" for a month, start and end dates otherwise."""
    if period.is_whole_months and period.first_month == period.last_month:
        return f"nodus-transacciones-{period.start:%Y-%m}.csv"
    return f"nodus-transacciones-{period.start:%Y-%m-%d}_{period.end:%Y-%m-%d}.csv"


class TransactionsPage(Page):
    """The movements of a period, newest first, narrowed by account, category, payee, tag,
    type or text, with what they add up to at the foot.

    The list itself (row menus, choosing several rows) is a ``TransactionListView``. Each
    list filter ends with «Editar», which asks for the page that manages that list.
    """

    navigate_requested = Signal(object)  # PageId

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__("Transacciones")
        self._services = services
        self._event_bus = event_bus
        self._theme_manager = theme_manager

        # The period goes in the header, as on the dashboard, to leave the row to the filters.
        self.period_selector = PeriodSelector()
        self.add_header_widget(self.period_selector)
        self.export_button = self.add_header_button("Exportar")
        self.export_button.setToolTip("Guarda en un archivo CSV los movimientos que se ven")
        self.export_button.clicked.connect(self.export_shown)
        self.account_filter = AccountComboBox()
        self.category_filter = CategoryComboBox()
        self.payee_filter = PayeeComboBox()
        self.tag_filter = TagComboBox()
        for combo, page_id in (
            (self.account_filter, PageId.ACCOUNTS),
            (self.category_filter, PageId.CATEGORIES),
            (self.payee_filter, PageId.PAYEES),
            (self.tag_filter, PageId.TAGS),
        ):
            combo.enable_manage_item()
            combo.manage_requested.connect(partial(self.navigate_requested.emit, page_id))
        self.type_filter = ComboBox()
        self.type_filter.addItems(list(TYPE_FILTERS))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar…")
        self.search_input.setToolTip(
            "Busca en la nota y en los nombres del beneficiario y las etiquetas"
        )
        self.search_input.setMinimumWidth(140)
        self.search_input.setClearButtonEnabled(True)
        self.clear_filters_button = QPushButton("Limpiar filtros")
        self.clear_filters_button.setObjectName("SecondaryButton")
        self.clear_filters_button.clicked.connect(self.clear_filters)
        filters = QHBoxLayout()
        filters.setSpacing(Space.S)
        for widget in self._filter_combos():
            filters.addWidget(widget)
        filters.addWidget(self.search_input, stretch=1)
        filters.addWidget(self.clear_filters_button)
        self.content_layout.addLayout(filters)

        self.list_view = TransactionListView(services, event_bus, theme_manager, self)
        self.content_layout.addWidget(self.list_view, stretch=1)
        # The list's parts, at hand as the page's own.
        view = self.list_view
        self.model, self.table, self.empty_state = view.model, view.table, view.empty_state
        self.totals_label, self.selection_bar = view.totals_label, view.selection_bar
        self.edit_button, self.delete_button = view.edit_button, view.delete_button
        self.row_actions, self.selected_items = view.row_actions, view.selected_items
        self.delete_selected = view.delete_selected

        self.period_selector.period_changed.connect(self.reload)
        self.account_filter.currentIndexChanged.connect(self.reload)
        self.category_filter.currentIndexChanged.connect(self.reload)
        self.payee_filter.currentIndexChanged.connect(self.reload)
        self.tag_filter.currentIndexChanged.connect(self.reload)
        self.type_filter.currentIndexChanged.connect(self.reload)
        self.search_input.textChanged.connect(self.reload)
        for signal in (
            event_bus.transactions_changed,
            event_bus.accounts_changed,
            event_bus.categories_changed,
            event_bus.payees_changed,
            event_bus.tags_changed,
            event_bus.exchange_rates_changed,
        ):
            signal.connect(self.refresh)

    def refresh(self) -> None:
        """Reloads the filter choices (keeping the selection) and then the movements."""
        self._load_filter_choices()
        self.reload()

    def _load_filter_choices(self) -> None:
        self.account_filter.set_accounts(
            self._services.accounts.list_accounts(include_archived=True), "Cuenta"
        )
        categories = self._services.categories
        self.category_filter.set_categories(
            [
                ("Gastos", categories.category_tree(TransactionType.EXPENSE)),
                ("Ingresos", categories.category_tree(TransactionType.INCOME)),
            ],
            "Categoría",
        )
        self.payee_filter.set_payees(self._services.payees.list_payees(), "Beneficiario")
        self.tag_filter.set_tags(self._services.tags.list_tags(), "Etiqueta")

    def reload(self) -> None:
        """Lists the movements matching the current filters."""
        self.list_view.show_matching(self.current_filter())
        if self._has_filters():
            self.empty_state.set_message(
                "Sin transacciones con estos filtros", "Limpiar filtros", self.clear_filters
            )
        else:
            self.empty_state.set_message("Sin transacciones en este período")
        self.clear_filters_button.setEnabled(self._has_filters())
        for combo in self._filter_combos():
            set_style_property(combo, "filter", "active" if combo.currentIndex() > 0 else "idle")

    def clear_filters(self) -> None:
        """Back to every movement of the period shown; the period itself is kept."""
        self._reset_filters()
        self.reload()

    def focus(self, focus: TransactionFocus) -> None:
        """Shows the period of ``focus`` with only its account, category, payee or tag
        filtered, as other pages ask for.

        Does not reload: the caller shows the page, which refreshes it.
        """
        self._load_filter_choices()
        self._reset_filters()
        self.period_selector.blockSignals(True)
        self.period_selector.set_period(focus.period)
        self.period_selector.blockSignals(False)
        for combo, item_id in (
            (self.account_filter, focus.account_id),
            (self.category_filter, focus.category_id),
            (self.payee_filter, focus.payee_id),
            (self.tag_filter, focus.tag_id),
        ):
            if item_id is not None:
                combo.blockSignals(True)
                combo.select(item_id)
                combo.blockSignals(False)

    def _filter_combos(self) -> tuple[ComboBox, ...]:
        return (
            self.account_filter,
            self.category_filter,
            self.payee_filter,
            self.tag_filter,
            self.type_filter,
        )

    def _reset_filters(self) -> None:
        inputs = (*self._filter_combos(), self.search_input)
        for widget in inputs:  # one reload at the end instead of one per filter
            widget.blockSignals(True)
        for combo in self._filter_combos():
            combo.setCurrentIndex(0)
        self.search_input.clear()
        for widget in inputs:
            widget.blockSignals(False)

    def export_shown(self) -> None:
        """Exports what the table shows: the period with its filters."""
        export_transactions(
            self.window(),
            self._services,
            self._services.transactions.list_transactions(self.current_filter()),
            export_filename(self.period_selector.period()),
        )

    def _has_filters(self) -> bool:
        has_choice = any(combo.currentIndex() > 0 for combo in self._filter_combos())
        return has_choice or bool(self.search_input.text())

    def current_filter(self) -> TransactionFilter:
        period = self.period_selector.period()
        transaction_type, is_transfer, refund_linked = TYPE_FILTERS[self.type_filter.currentText()]
        return TransactionFilter(
            start=period.start,
            end=period.end,
            account_id=self.account_filter.current_id(),
            category_id=self.category_filter.current_id(),
            payee_id=self.payee_filter.current_id(),
            tag_id=self.tag_filter.current_id(),
            type=transaction_type,
            is_transfer=is_transfer,
            refund_linked=refund_linked,
            text=self.search_input.text().strip() or None,
        )
