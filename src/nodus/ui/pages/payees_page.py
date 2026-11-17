"""Payees section: who the user pays and who pays them, with what each adds up to."""

from __future__ import annotations

from nodus.services.classification.payee_service import PayeeSummary
from nodus.services.container import Services
from nodus.services.sorting import name_sort_key
from nodus.ui.actions.payees import delete_payees
from nodus.ui.dialogs.payee_dialogs import MergePayeeDialog, PayeeDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import TransactionFocus, history_period
from nodus.ui.pages.base.summary_page import TOTAL, SummaryPage, SummaryTableModel
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.inputs.color import color_icon

CATEGORY = TOTAL + 1
NO_PAYEES_TEXT = (
    "Todavía no hay beneficiarios: se crean al escribir uno nuevo al cargar un movimiento."
)
NO_MATCHES_TEXT = "Ningún beneficiario coincide con la búsqueda."


class PayeeTableModel(SummaryTableModel[PayeeSummary]):
    """Payee summaries, with the category used most with each."""

    TITLES = [*SummaryTableModel.TITLES, "Categoría habitual"]

    def name(self, summary: PayeeSummary) -> str:
        return summary.payee.name

    def extra_text(self, summary: PayeeSummary, column: int) -> str:
        category = summary.top_category
        return category.name if category else "—"

    def extra_sort(self, summary: PayeeSummary, column: int) -> object:
        category = summary.top_category
        return name_sort_key(category.name) if category else ""

    def decoration(self, summary: PayeeSummary, column: int) -> object:
        category = summary.top_category
        return color_icon(category.color) if column == CATEGORY and category else None


class PayeesPage(SummaryPage[PayeeSummary]):
    """Every payee with its number of movements, net total and usual category; its
    movements open over its whole history."""

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__(
            "Beneficiarios",
            "beneficiario",
            (NO_PAYEES_TEXT, NO_MATCHES_TEXT),
            PayeeTableModel(theme_manager.theme),
            theme_manager,
            chosen_word="seleccionados",
        )
        self._services = services
        self._event_bus = event_bus

    def load_summaries(self) -> list[PayeeSummary]:
        return self._services.payees.summaries()

    def item_id(self, summary: PayeeSummary) -> int:
        return summary.payee.id

    def focus_of(self, summary: PayeeSummary) -> TransactionFocus:
        period = history_period(summary.first_on, summary.last_on)
        return TransactionFocus(period, payee_id=summary.payee.id)

    def create_item(self) -> None:
        PayeeDialog(self._services, self._event_bus, parent=self.window()).exec()

    def edit_item(self, summary: PayeeSummary) -> None:
        PayeeDialog(self._services, self._event_bus, summary.payee, parent=self.window()).exec()

    def merge_items(self, summaries: list[PayeeSummary]) -> None:
        payees = [summary.payee for summary in summaries]
        MergePayeeDialog(self._services, self._event_bus, payees, parent=self.window()).exec()

    def delete_items(self, summaries: list[PayeeSummary]) -> None:
        delete_payees(self.window(), self._services, self._event_bus, summaries)
