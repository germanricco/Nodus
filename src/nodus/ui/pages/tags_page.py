"""Tags section: groups of movements across categories, such as a trip, and their totals."""

from __future__ import annotations

from nodus.services.container import Services
from nodus.services.tag_service import TagSummary
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.dialogs.tag_dialogs import MergeTagDialog, TagDialog, announce_tag_change
from nodus.ui.event_bus import EventBus
from nodus.ui.labels import movements_text
from nodus.ui.navigation import TransactionFocus, history_period
from nodus.ui.pages.summary_page import NAME, SummaryPage, SummaryTableModel
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.color import color_icon

NO_TAGS_TEXT = (
    "Aún no hay etiquetas: se crean al escribir una nueva al cargar un movimiento,"
    " o con «Crear etiqueta»."
)
NO_MATCHES_TEXT = "Ninguna etiqueta coincide con la búsqueda"


class TagTableModel(SummaryTableModel[TagSummary]):
    """Tag summaries, each name with its color."""

    def name(self, summary: TagSummary) -> str:
        return summary.tag.name

    def decoration(self, summary: TagSummary, column: int) -> object:
        return color_icon(summary.tag.color) if column == NAME else None


class TagsPage(SummaryPage[TagSummary]):
    """Every tag with its number of movements and net total; its movements open over its
    whole history."""

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__(
            "Etiquetas",
            "etiqueta",
            (NO_TAGS_TEXT, NO_MATCHES_TEXT),
            TagTableModel(theme_manager.theme),
            theme_manager,
        )
        self._services = services
        self._event_bus = event_bus
        for signal in (
            event_bus.tags_changed,
            event_bus.transactions_changed,
            event_bus.exchange_rates_changed,
        ):
            signal.connect(self.refresh)

    def load_summaries(self) -> list[TagSummary]:
        return self._services.tags.summaries()

    def focus_of(self, summary: TagSummary) -> TransactionFocus:
        period = history_period(summary.first_on, summary.last_on)
        return TransactionFocus(period, tag_id=summary.tag.id)

    def create_item(self) -> None:
        TagDialog(self._services, self._event_bus, parent=self.window()).exec()

    def edit_item(self, summary: TagSummary) -> None:
        TagDialog(self._services, self._event_bus, summary.tag, parent=self.window()).exec()

    def merge_items(self, summaries: list[TagSummary]) -> None:
        tags = [summary.tag for summary in summaries]
        MergeTagDialog(self._services, self._event_bus, tags, parent=self.window()).exec()

    def delete_items(self, summaries: list[TagSummary]) -> None:
        if len(summaries) == 1:
            title, text = "Eliminar etiqueta", f"Se va a eliminar «{summaries[0].tag.name}»."
            count = summaries[0].count
        else:
            title = "Eliminar etiquetas"
            text = f"Se van a eliminar {len(summaries)} etiquetas."
            count = self._services.tags.tagged_count([summary.tag.id for summary in summaries])
        if count:
            lose = "la pierden" if len(summaries) == 1 else "pierden alguna"
            text += f" {movements_text(count)} {lose}; los movimientos no se borran."
        if confirm(self.window(), title, text):
            self._services.tags.delete_many([summary.tag.id for summary in summaries])
            announce_tag_change(self._event_bus)
