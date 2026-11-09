"""Payees section: who the user pays and who pays them, with what each adds up to."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from nodus.services.container import Services
from nodus.services.payee_service import PayeeSummary
from nodus.services.sorting import name_sort_key
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.dialogs.payee_dialogs import MergePayeeDialog, PayeeDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.labels import movements_text
from nodus.ui.navigation import TransactionFocus, history_period
from nodus.ui.pages.summary_page import TOTAL, SummaryPage, SummaryTableModel
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.color import color_icon

CATEGORY = TOTAL + 1
NO_PAYEES_TEXT = "Aún no hay beneficiarios: se crean al escribir uno nuevo al cargar un movimiento."
NO_MATCHES_TEXT = "Ningún beneficiario coincide con la búsqueda"


def payee_delete_warning(summaries: list[PayeeSummary]) -> str:
    """What deleting payees does: their movements stay, without a payee."""
    if len(summaries) == 1:
        text = f"Se va a eliminar «{summaries[0].payee.name}»."
    else:
        text = f"Se van a eliminar {len(summaries)} beneficiarios."
    count = sum(summary.count for summary in summaries)
    if count:
        left = "queda" if count == 1 else "quedan"
        text += f" {movements_text(count)} {left} sin beneficiario."
    return text


def delete_payees(
    parent: QWidget, services: Services, event_bus: EventBus, summaries: list[PayeeSummary]
) -> bool:
    """Deletes the payees of ``summaries`` once the user confirms."""
    title = (
        "Eliminar beneficiario"
        if len(summaries) == 1
        else f"Eliminar {len(summaries)} beneficiarios"
    )
    if not confirm(parent, title, payee_delete_warning(summaries)):
        return False
    services.payees.delete_many([summary.payee.id for summary in summaries])
    event_bus.payees_changed.emit()
    event_bus.transactions_changed.emit()
    return True


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
        for signal in (
            event_bus.payees_changed,
            event_bus.transactions_changed,
            event_bus.categories_changed,
            event_bus.exchange_rates_changed,
        ):
            signal.connect(self.refresh)

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
