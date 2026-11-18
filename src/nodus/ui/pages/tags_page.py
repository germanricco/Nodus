"""Tags section: groups of movements across categories, such as a trip, and their totals."""

from __future__ import annotations

from nodus.i18n import N_, _
from nodus.services.classification.tag_service import TagSummary
from nodus.services.container import Services
from nodus.ui.actions.tags import delete_tags
from nodus.ui.dialogs.tag_dialogs import MergeTagDialog, TagDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import TransactionFocus, history_period
from nodus.ui.pages.base.summary_page import NAME, SummaryPage, SummaryTableModel
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.inputs.color import color_icon

NO_TAGS_TEXT = N_(
    "Todavía no hay etiquetas: se crean al escribir una nueva al cargar un movimiento."
)
NO_MATCHES_TEXT = N_("Ninguna etiqueta coincide con la búsqueda.")


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
            _("Etiquetas"),
            N_("etiqueta"),
            (NO_TAGS_TEXT, NO_MATCHES_TEXT),
            TagTableModel(theme_manager.theme),
            theme_manager,
        )
        self._services = services
        self._event_bus = event_bus

    def load_summaries(self) -> list[TagSummary]:
        return self._services.tags.summaries()

    def item_id(self, summary: TagSummary) -> int:
        return summary.tag.id

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
        delete_tags(self.window(), self._services, self._event_bus, summaries)
