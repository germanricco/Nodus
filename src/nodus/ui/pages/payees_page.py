"""Payees section: who the user pays and who pays them, with what each adds up to."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout

from nodus.i18n import N_, _
from nodus.models.period import Period
from nodus.models.transaction import TransactionType
from nodus.services.classification.payee_service import PayeeSummary
from nodus.services.container import Services
from nodus.services.sorting import name_sort_key
from nodus.ui.actions.payees import delete_payees
from nodus.ui.dialogs.payee_dialogs import MergePayeeDialog, PayeeDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import TransactionFocus, history_period
from nodus.ui.pages.base.summary_page import NAME, TOTAL, SummaryPage, SummaryTableModel
from nodus.ui.text.labels import KIND_TITLES
from nodus.ui.theme.design import RowRole
from nodus.ui.theme.theme_manager import ThemeManager, active_theme
from nodus.ui.widgets.initial_badge import initial_pixmap
from nodus.ui.widgets.inputs.color import color_icon
from nodus.ui.widgets.inputs.segmented import SegmentedControl

CATEGORY = TOTAL + 1
NO_PAYEES_TEXT = N_(
    "Todavía no hay beneficiarios: se crean al escribir uno nuevo al cargar un movimiento."
)
NO_MATCHES_TEXT = N_("Ningún beneficiario coincide con la búsqueda.")
# When the other side has payees and this one has none.
NO_KIND_TEXTS = {
    TransactionType.EXPENSE: N_("Todavía no hay beneficiarios de gastos."),
    TransactionType.INCOME: N_(
        "Todavía no hay beneficiarios de ingresos: los que te pagan, como tu empleador."
    ),
}
KINDS = (TransactionType.EXPENSE, TransactionType.INCOME)


class PayeeTableModel(SummaryTableModel[PayeeSummary]):
    """Payee summaries, with the category used most with each. Each name has its
    initial in the color of that category, gray without one (plan 029a, 5.6)."""

    TITLES = [*SummaryTableModel.TITLES, N_("Categoría habitual")]

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
        if column == NAME:
            color = category.color if category else active_theme().text_muted
            return initial_pixmap(summary.payee.name, color)
        return color_icon(category.color) if column == CATEGORY and category else None


class PayeesPage(SummaryPage[PayeeSummary]):
    """The payees of one side, chosen over the table: those the user pays or those that
    pay them (``PayeeSummary.kind``), each with its number of movements, net total and
    usual category; its movements open over its whole history."""

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__(
            _("Beneficiarios"),
            N_("beneficiario"),
            (NO_PAYEES_TEXT, NO_MATCHES_TEXT),
            PayeeTableModel(theme_manager.theme),
            theme_manager,
            chosen_word=N_("seleccionados"),
        )
        self._services = services
        self._event_bus = event_bus
        self.kind_input = SegmentedControl([_(KIND_TITLES[kind]) for kind in KINDS])
        self.kind_input.changed.connect(lambda _index: self.refresh())
        kind_row = QHBoxLayout()
        kind_row.addWidget(self.kind_input)
        kind_row.addStretch()
        self.content_layout.insertLayout(0, kind_row)
        # Each row starts with its initial, as a movement does: the same height.
        self.table.verticalHeader().setDefaultSectionSize(RowRole.DOUBLE)

    @property
    def kind(self) -> TransactionType:
        """The side shown."""
        return KINDS[self.kind_input.index()]

    def load_summaries(self, period: Period) -> list[PayeeSummary]:
        every = self._services.payees.summaries(period)
        shown = [summary for summary in every if summary.kind is self.kind]
        self._no_items_text = NO_KIND_TEXTS[self.kind] if every else NO_PAYEES_TEXT
        return shown

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
