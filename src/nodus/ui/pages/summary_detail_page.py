"""The page about a payee or a tag: its key figures and every movement it has."""

from __future__ import annotations

from typing import Generic

from PySide6.QtWidgets import QLabel

from nodus.models.transaction_filter import TransactionFilter
from nodus.services.container import Services
from nodus.services.errors import NotFoundError
from nodus.ui.event_bus import EventBus
from nodus.ui.formatting import format_date
from nodus.ui.labels import unconverted_note
from nodus.ui.navigation import DetailId
from nodus.ui.pages.dashboard_cards import FigureTile
from nodus.ui.pages.detail_page import DetailPage, danger_zone
from nodus.ui.pages.summary_page import S
from nodus.ui.pages.transaction_list_view import TransactionListView
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.figure_row import FigureRow
from nodus.ui.widgets.money_label import masked

NO_MOVEMENTS = "—"


class SummaryDetailPage(DetailPage, Generic[S]):
    """A payee or a tag at a glance: how many movements it has, what they add up to and
    when the latest was, then every one of them over its whole history, with the same
    menus and selection as Transacciones.

    «Editar» and «Unir con…» are in the header; deleting is in the «Zona de peligro».
    Subclasses load the item and carry out the actions; ``CAPTIONS`` name the figures
    after the shared ones, which ``extra_figures`` fills.
    """

    CAPTIONS: tuple[str, ...] = ()

    def __init__(
        self,
        detail_id: DetailId,
        services: Services,
        event_bus: EventBus,
        theme_manager: ThemeManager,
        delete_action: str,
    ) -> None:
        super().__init__(detail_id, theme_manager)
        self._services = services
        self._event_bus = event_bus
        self._hidden = services.settings.amounts_hidden()
        self.summary: S | None = None

        self.edit_button = self.add_header_button("Editar")
        self.edit_button.clicked.connect(lambda: self.edit_item(self.summary))
        self.merge_button = self.add_header_button("Unir con…")
        self.merge_button.setToolTip("Le pasa sus movimientos a otro y lo elimina")
        self.merge_button.clicked.connect(lambda: self.merge_item(self.summary))

        self.figures = FigureRow()
        self.figure_labels: dict[str, QLabel] = {}
        for caption in ("Movimientos", "Total", "Último movimiento", *self.CAPTIONS):
            label = QLabel()
            self.figure_labels[caption] = label
            self.figures.add_tile(FigureTile(caption, label, large=True))
        self.content_layout.addWidget(self.figures)

        self.list_view = TransactionListView(services, event_bus, theme_manager, self)
        self.list_view.empty_state.set_message("Todavía no tiene movimientos.")
        self.content_layout.addWidget(self.list_view, stretch=1)

        self.danger_card, self.delete_button = danger_zone("", delete_action, self._delete)
        self._danger_text = self.danger_card.findChild(QLabel, "FieldHint")
        self.content_layout.addWidget(self.danger_card)

        for signal in (
            event_bus.transactions_changed,
            event_bus.exchange_rates_changed,
            event_bus.categories_changed,
            event_bus.payees_changed,
            event_bus.tags_changed,
            event_bus.accounts_changed,
        ):
            signal.connect(self._data_changed)
        event_bus.amounts_hidden_changed.connect(self._set_amounts_hidden)

    # To implement

    def load_summary(self, item_id: int) -> S:
        """The item with its totals; NotFoundError once it was deleted or merged."""
        raise NotImplementedError

    def name(self, summary: S) -> str:
        raise NotImplementedError

    def criteria(self, summary: S) -> TransactionFilter:
        """Its movements, over its whole history."""
        raise NotImplementedError

    def extra_figures(self, summary: S) -> list[str]:
        """The values of ``CAPTIONS``, in their order."""
        return []

    def has_others(self) -> bool:
        """Whether there is another item to merge this one with."""
        raise NotImplementedError

    def edit_item(self, summary: S) -> None:
        raise NotImplementedError

    def merge_item(self, summary: S) -> None:
        raise NotImplementedError

    def delete_warning(self, summary: S) -> str:
        raise NotImplementedError

    def delete_item(self, summary: S) -> bool:
        """Deletes the item once the user confirms; True if it was deleted."""
        raise NotImplementedError

    # Shared

    def refresh(self) -> None:
        if self.item_id is None:
            return
        try:
            summary = self.summary = self.load_summary(self.item_id)
        except NotFoundError:
            self.back_requested.emit()
            return
        self.title_label.setText(self.name(summary))
        self.merge_button.setEnabled(self.has_others())
        values = [
            str(summary.count),
            self._total_text(summary),
            format_date(summary.last_on) if summary.last_on else NO_MOVEMENTS,
            *self.extra_figures(summary),
        ]
        for label, value in zip(self.figure_labels.values(), values, strict=True):
            label.setText(value)
        self.figures.relayout()
        self.list_view.show_matching(self.criteria(summary))
        self._danger_text.setText(self.delete_warning(summary))

    def _total_text(self, summary: S) -> str:
        """Income minus expenses in pesos; the tooltip counts what lacks a rate."""
        note = unconverted_note(summary.unconverted) if summary.unconverted else ""
        self.figure_labels["Total"].setToolTip(note)
        if not summary.count:
            return NO_MOVEMENTS
        return masked(summary.net) if self._hidden else summary.net.format()

    def _delete(self) -> None:
        if self.delete_item(self.summary):
            self.back_requested.emit()

    def _data_changed(self) -> None:
        # Hidden, it is refreshed when shown again.
        if self.isVisible():
            self.refresh()

    def _set_amounts_hidden(self, hidden: bool) -> None:
        self._hidden = hidden
        self._data_changed()
