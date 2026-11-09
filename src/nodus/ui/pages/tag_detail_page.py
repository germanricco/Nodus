"""The page about one tag: its figures and every movement that carries it."""

from __future__ import annotations

from nodus.models.transaction_filter import TransactionFilter
from nodus.services.container import Services
from nodus.services.tag_service import TagSummary
from nodus.ui.dialogs.tag_dialogs import MergeTagDialog, TagDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.formatting import format_date
from nodus.ui.navigation import DetailId
from nodus.ui.pages.summary_detail_page import NO_MOVEMENTS, SummaryDetailPage
from nodus.ui.pages.tags_page import delete_tags, tag_delete_warning
from nodus.ui.theme.theme_manager import ThemeManager


class TagDetailPage(SummaryDetailPage[TagSummary]):
    """A tag, such as a trip, with when its first movement was; deleting it keeps the
    movements, without the tag."""

    CAPTIONS = ("Primer movimiento",)

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__(DetailId.TAG, services, event_bus, theme_manager, "Eliminar etiqueta")

    def load_summary(self, item_id: int) -> TagSummary:
        return self._services.tags.summary(item_id)

    def name(self, summary: TagSummary) -> str:
        return summary.tag.name

    def criteria(self, summary: TagSummary) -> TransactionFilter:
        return TransactionFilter(tag_id=summary.tag.id)

    def extra_figures(self, summary: TagSummary) -> list[str]:
        return [format_date(summary.first_on) if summary.first_on else NO_MOVEMENTS]

    def has_others(self) -> bool:
        return len(self._services.tags.list_tags()) > 1

    def edit_item(self, summary: TagSummary) -> None:
        TagDialog(self._services, self._event_bus, summary.tag, parent=self.window()).exec()

    def merge_item(self, summary: TagSummary) -> None:
        MergeTagDialog(self._services, self._event_bus, [summary.tag], parent=self.window()).exec()

    def delete_warning(self, summary: TagSummary) -> str:
        return tag_delete_warning(self._services, [summary])

    def delete_item(self, summary: TagSummary) -> bool:
        return delete_tags(self.window(), self._services, self._event_bus, [summary])
