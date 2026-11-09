"""The page about one payee: its figures, usual category and every movement."""

from __future__ import annotations

from nodus.models.transaction_filter import TransactionFilter
from nodus.services.container import Services
from nodus.services.payee_service import PayeeSummary
from nodus.ui.dialogs.payee_dialogs import MergePayeeDialog, PayeeDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import DetailId
from nodus.ui.pages.payees_page import delete_payees, payee_delete_warning
from nodus.ui.pages.summary_detail_page import NO_MOVEMENTS, SummaryDetailPage
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.transaction_table import PAYEE


class PayeeDetailPage(SummaryDetailPage[PayeeSummary]):
    """A payee with the category used most with it; deleting keeps its movements."""

    CAPTIONS = ("Categoría habitual",)

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__(
            DetailId.PAYEE, services, event_bus, theme_manager, "Eliminar beneficiario"
        )
        # Every row would repeat the payee.
        self.list_view.table.setColumnHidden(PAYEE, True)

    def load_summary(self, item_id: int) -> PayeeSummary:
        return self._services.payees.summary(item_id)

    def name(self, summary: PayeeSummary) -> str:
        return summary.payee.name

    def criteria(self, summary: PayeeSummary) -> TransactionFilter:
        return TransactionFilter(payee_id=summary.payee.id)

    def extra_figures(self, summary: PayeeSummary) -> list[str]:
        category = summary.top_category
        return [category.name if category else NO_MOVEMENTS]

    def has_others(self) -> bool:
        return len(self._services.payees.list_payees()) > 1

    def edit_item(self, summary: PayeeSummary) -> None:
        PayeeDialog(self._services, self._event_bus, summary.payee, parent=self.window()).exec()

    def merge_item(self, summary: PayeeSummary) -> None:
        MergePayeeDialog(
            self._services, self._event_bus, [summary.payee], parent=self.window()
        ).exec()

    def delete_warning(self, summary: PayeeSummary) -> str:
        return payee_delete_warning([summary])

    def delete_item(self, summary: PayeeSummary) -> bool:
        return delete_payees(self.window(), self._services, self._event_bus, [summary])
