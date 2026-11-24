"""The page about a category, a payee or a tag: what it added up to in the last year,
and every movement it has."""

from __future__ import annotations

from datetime import date
from typing import Generic

from PySide6.QtWidgets import QLabel, QWidget

from nodus.i18n import N_, _
from nodus.models.period import RECENT_MONTHS, Period
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.container import Services
from nodus.services.errors import NotFoundError
from nodus.ui.dialogs.transaction_dialog import TransactionStart
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import DetailId
from nodus.ui.pages.base.detail_page import DetailPage
from nodus.ui.pages.base.summary_page import S
from nodus.ui.pages.base.transaction_list_view import TransactionListView
from nodus.ui.text.formatting import format_date
from nodus.ui.text.labels import unconverted_note
from nodus.ui.theme.design import Layout
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.figure_row import FigureRow
from nodus.ui.widgets.figure_tile import FigureTile
from nodus.ui.widgets.hero_figure import HeroFigure
from nodus.ui.widgets.money_label import masked
from nodus.ui.widgets.tables.row_actions import Effect, MoreButton, RowAction

NO_MOVEMENTS = "—"
MOVEMENTS = N_("Movimientos")


class SummaryDetailPage(DetailPage, Generic[S]):
    """A category, a payee or a tag at a glance: what its movements added up to in the
    last ``RECENT_MONTHS`` months and how many they were, a stretch with a clear start and
    end, and when the latest was; then every one of them over its whole history, with the
    same menus and selection as Transacciones.

    «Editar» and «Unir con…» are in the header; deleting, the rare one, in its «⋯».
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
    ) -> None:
        super().__init__(detail_id, theme_manager)
        self._services = services
        self._event_bus = event_bus
        self._hidden = services.settings.amounts_hidden()
        self.summary: S | None = None
        self.today: date | None = None  # fixed by tests; otherwise the real date

        self.edit_button = self.add_header_button(_("Editar"))
        self.edit_button.clicked.connect(lambda: self.edit_item(self.summary))
        self.merge_button = self.add_header_button(_("Unir con…"))
        self.merge_button.setToolTip(_("Le pasa sus movimientos a otro y lo elimina"))
        self.merge_button.clicked.connect(lambda: self.merge_item(self.summary))
        self.more_button = MoreButton(self.more_actions)
        self.add_header_widget(self.more_button)

        # The page scrolls, as an account's: in a short window every card keeps its height
        # and the movements keep room below them, instead of all of them being squeezed.
        self.body = self.scrolling_body()
        # Keyed by the untranslated caption, which the code looks up; filled in this order.
        self.figure_labels: dict[str, QLabel] = {N_("Total"): QLabel()}
        # The total answers the page; the rest go in boxes under it.
        total_caption = _("Total de los últimos {count} meses").format(count=RECENT_MONTHS)
        self.body.addWidget(HeroFigure(total_caption, self.figure_labels["Total"]))
        self.figures = FigureRow()
        for caption in (MOVEMENTS, N_("Último movimiento"), *self.CAPTIONS):
            label = QLabel()
            self.figure_labels[caption] = label
            badge = self.figure_badge(caption)
            self.figures.add_tile(FigureTile(self._caption(caption), label, badge, True))
        self.body.addWidget(self.figures)

        self.list_view = TransactionListView(services, event_bus, theme_manager, self)
        self.list_view.setMinimumHeight(Layout.DETAIL_LIST_MIN_HEIGHT)
        self.body.addWidget(self.list_view, stretch=1)

        event_bus.amounts_hidden_changed.connect(self._set_amounts_hidden)

    @staticmethod
    def _caption(caption: str) -> str:
        """The movements are counted in the same months as the total."""
        if caption == MOVEMENTS:
            return _("Movimientos en {count} meses").format(count=RECENT_MONTHS)
        return _(caption)

    def recent(self) -> Period:
        """The months the page adds up."""
        return Period.recent(self.today or date.today())

    # To implement

    def load_summary(self, item_id: int) -> S:
        """The item with its totals in ``recent()``; NotFoundError once it was deleted or
        merged."""
        raise NotImplementedError

    def name(self, summary: S) -> str:
        raise NotImplementedError

    def criteria(self, summary: S) -> TransactionFilter:
        """Its movements, over its whole history."""
        raise NotImplementedError

    def figure_badge(self, caption: str) -> QWidget | None:
        """A badge for the tile of ``caption`` (untranslated), such as a change, beside its
        figure; none by default. Called while the page is built."""
        return None

    def extra_figures(self, summary: S) -> list[str]:
        """The values of ``CAPTIONS``, in their order."""
        return []

    def transaction_start(self, summary: S) -> TransactionStart:
        """A new movement with this item already in its field."""
        raise NotImplementedError

    def has_others(self) -> bool:
        """Whether there is another item to merge this one with."""
        raise NotImplementedError

    def edit_item(self, summary: S) -> None:
        raise NotImplementedError

    def merge_item(self, summary: S) -> None:
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
            self.summary = None
            self.back_requested.emit()
            return
        self.title_label.setText(self.name(summary))
        start = self.transaction_start(summary)
        self.list_view.empty_state.set_message(
            _("Todavía no tiene movimientos."),
            _("Agregar transacción"),
            lambda: self.new_transaction_requested.emit(start),
        )
        self.merge_button.setEnabled(self.has_others())
        values = [
            self._total_text(summary),
            str(summary.totals.count),
            format_date(summary.last_on) if summary.last_on else NO_MOVEMENTS,
            *self.extra_figures(summary),
        ]
        for label, value in zip(self.figure_labels.values(), values, strict=True):
            label.setText(value)
        self.figures.relayout()
        self.list_view.show_matching(self.criteria(summary))

    def _total_text(self, summary: S) -> str:
        """Its total in pesos; the tooltip counts what lacks a rate."""
        totals = summary.totals
        note = unconverted_note(totals.unconverted) if totals.unconverted else ""
        self.figure_labels["Total"].setToolTip(note)
        if not totals.count:
            return NO_MOVEMENTS
        return masked(totals.net) if self._hidden else totals.net.format()

    def more_actions(self) -> list[RowAction]:
        if self.summary is None:
            return []
        return [
            RowAction(
                _("Eliminar"), self.delete, "trash", destructive=True, effect=Effect.CONFIRMED
            )
        ]

    def delete(self) -> None:
        if self.delete_item(self.summary):
            self.back_requested.emit()

    def _set_amounts_hidden(self, hidden: bool) -> None:
        self._hidden = hidden
        self.request_refresh()
