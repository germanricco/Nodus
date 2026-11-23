"""The page about one category: what it adds up to, month by month, and its movements."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from nodus.i18n import N_, _
from nodus.models.currency import HOME_CURRENCY
from nodus.models.period import Month, Period, format_month
from nodus.models.transaction import TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.container import Services
from nodus.services.conversion import relative_change
from nodus.services.reports.category_report_service import CategorySummary
from nodus.ui.actions.categories import delete_categories
from nodus.ui.dialogs.category_dialog import CategoryDialog, MergeCategoryDialog
from nodus.ui.dialogs.transaction_dialog import TransactionStart
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import DetailId, TransactionFocus
from nodus.ui.pages.base.summary_detail_page import NO_MOVEMENTS, SummaryDetailPage
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card, card_header
from nodus.ui.widgets.change_badge import ChangeBadge
from nodus.ui.widgets.charts.chart_base import format_compact
from nodus.ui.widgets.charts.stacked_bar_chart import StackedBar, StackedBarChart, StackSegment
from nodus.ui.widgets.link_line import Link, LinkLine
from nodus.ui.widgets.money_label import amount_text
from nodus.ui.widgets.tables.row_actions import Effect, RowAction
from nodus.ui.widgets.tables.transaction_table import CATEGORY

THIS_MONTH = N_("Este mes")
HAS_SUBCATEGORIES_TEXT = N_("Para unirla, primero une o elimina sus subcategorías.")


class CategoryDetailPage(SummaryDetailPage[CategorySummary]):
    """A category with this month and its monthly average, a bar per month of the last
    year (a click opens that month's movements) and links to its subcategories or to the
    category it sits in. Amounts read as in Categorías: what was spent, or received.

    «Otros» and «Reembolsos» belong to Nodus, so their page only shows them.
    """

    CAPTIONS = (THIS_MONTH, N_("Promedio por mes"))

    transactions_requested = Signal(object)  # TransactionFocus
    category_requested = Signal(int)  # category id

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__(DetailId.CATEGORY, services, event_bus, theme_manager)
        self.today: date | None = None  # fixed by tests; otherwise the real date
        self.related_line = LinkLine()
        self.chart = StackedBarChart(
            theme_manager.theme, lambda cents: format_compact(cents, HOME_CURRENCY)
        )
        self.chart.clicked.connect(self._month_clicked)
        theme_manager.theme_changed.connect(self.chart.set_theme)
        chart_card = Card()
        card_header(chart_card, _("Mes a mes"))
        chart_card.body.addWidget(self.chart)
        at = self.content_layout.indexOf(self.list_view)
        self.content_layout.insertWidget(at, self.related_line)
        self.content_layout.insertWidget(at + 1, chart_card)

    def load_summary(self, item_id: int) -> CategorySummary:
        return self._services.category_report.summary(item_id, self.today or date.today())

    def name(self, summary: CategorySummary) -> str:
        return summary.category.name

    def criteria(self, summary: CategorySummary) -> TransactionFilter:
        return TransactionFilter(category_id=summary.category.id)

    def figure_badge(self, caption: str) -> QWidget | None:
        if caption != THIS_MONTH:
            return None
        self.change_badge = ChangeBadge(none_text=_("Nueva"))
        return self.change_badge

    def extra_figures(self, summary: CategorySummary) -> list[str]:
        average = summary.average
        return [
            amount_text(summary.this_month, self._hidden),
            amount_text(average, self._hidden) if average is not None else NO_MOVEMENTS,
        ]

    def transaction_start(self, summary: CategorySummary) -> TransactionStart:
        return TransactionStart(category_id=summary.category.id)

    def has_others(self) -> bool:
        return self.summary is not None and self._services.categories.can_merge(
            self.summary.category.id
        )

    def edit_item(self, summary: CategorySummary) -> None:
        CategoryDialog(
            self._services, self._event_bus, summary.category, parent=self.window()
        ).exec()

    def merge_item(self, summary: CategorySummary) -> None:
        MergeCategoryDialog(
            self._services, self._event_bus, [summary.category], parent=self.window()
        ).exec()

    def delete_item(self, summary: CategorySummary) -> bool:
        return delete_categories(self.window(), self._services, self._event_bus, [summary.category])

    def more_actions(self) -> list[RowAction]:
        summary = self.summary
        if summary is None or summary.category.is_fixed:
            return []
        category = summary.category
        actions = []
        if not category.is_subcategory:
            actions.append(
                RowAction(
                    _("Agregar subcategoría"),
                    lambda: CategoryDialog(
                        self._services,
                        self._event_bus,
                        kind=category.kind,
                        parent_id=category.id,
                        parent=self.window(),
                    ).exec(),
                    "plus",
                    effect=Effect.OPEN,
                )
            )
        return actions + super().more_actions()

    def refresh(self) -> None:
        super().refresh()
        summary = self.summary
        if summary is None:
            return
        category = summary.category
        managed = not category.is_fixed
        self.edit_button.setVisible(managed)
        self.merge_button.setVisible(managed)
        self.more_button.setVisible(managed)
        self.merge_button.setToolTip(
            _(HAS_SUBCATEGORIES_TEXT)
            if summary.children
            else _("Le pasa sus movimientos a otra y la elimina")
        )
        # A parent's movements may be in any of its subcategories, so its rows say which.
        self.list_view.table.setColumnHidden(CATEGORY, not summary.children)
        self._show_related(summary)
        self._show_months(summary)
        self._show_change(summary)

    def _show_related(self, summary: CategorySummary) -> None:
        """Its subcategories, or the category it sits in, each a link to its page."""
        category = summary.category
        if category.is_subcategory:
            parent = self._services.categories.get(category.parent_id)
            label, related = _("Dentro de:"), [parent]
        else:
            label, related = _("Subcategorías:"), summary.children
        self.related_line.set_links(
            label,
            [
                Link(
                    c.name, _("Abrir la categoría"), lambda i=c.id: self.category_requested.emit(i)
                )
                for c in related
            ],
        )

    def _show_months(self, summary: CategorySummary) -> None:
        color = summary.category.color
        self.chart.set_bars(
            [
                StackedBar(
                    month.short_name,
                    (StackSegment(summary.category.id, color, total.cents),),
                    format_month(month),
                    (amount_text(total, self._hidden),),
                    month,
                )
                for month, total in summary.months
            ],
            summary.average.cents if summary.average is not None else None,
        )

    def _show_change(self, summary: CategorySummary) -> None:
        """This month against the one before, as Inicio compares each category: more
        spending is bad news, more income good news; «Nueva» when the month before had
        nothing, and no badge when neither had anything."""
        this_month, previous = summary.this_month, summary.months[-2][1]
        badge = self.change_badge
        badge.set_higher_is_better(summary.category.kind is TransactionType.INCOME)
        badge.set_change(relative_change(this_month, previous))
        badge.setToolTip(
            _("Mes anterior: {amount}").format(amount=amount_text(previous, self._hidden))
        )
        if this_month.is_zero and previous.is_zero:
            badge.hide()
        # The badge widens its tile, which may need a row of its own now.
        self.figures.relayout()

    def _month_clicked(self, index: int, _key: object) -> None:
        summary = self.summary
        if summary is None:
            return
        month: Month = summary.months[index][0]
        self.transactions_requested.emit(
            TransactionFocus(Period.of_months(month), category_id=summary.category.id)
        )
