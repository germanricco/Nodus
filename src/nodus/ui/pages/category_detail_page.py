"""The page about one category: what it adds up to, month by month, and its movements."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from nodus.i18n import N_, _
from nodus.models.money import Money
from nodus.models.period import Month, Period, format_month
from nodus.models.transaction import TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.container import Services
from nodus.services.conversion import relative_change
from nodus.services.reports.category_report_service import CategoryPart, CategorySummary
from nodus.ui.actions.categories import delete_categories
from nodus.ui.dialogs.category_dialog import CategoryDialog, MergeCategoryDialog
from nodus.ui.dialogs.transaction_dialog import TransactionStart
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import DetailId, RecordLink, TransactionFocus
from nodus.ui.pages.base.summary_detail_page import NO_MOVEMENTS, SummaryDetailPage
from nodus.ui.text.formatting import percent
from nodus.ui.text.labels import movements_text
from nodus.ui.theme.design import Chart
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card, card_header
from nodus.ui.widgets.change_badge import ChangeBadge
from nodus.ui.widgets.charts.chart_base import compact_pesos, distinct_colors
from nodus.ui.widgets.charts.stacked_bar_chart import StackedBar, StackedBarChart, StackSegment
from nodus.ui.widgets.link_line import Link, LinkLine
from nodus.ui.widgets.money_label import amount_text
from nodus.ui.widgets.style import amount_label, clear_layout, muted_label
from nodus.ui.widgets.tables.category_line import CategoryLine
from nodus.ui.widgets.tables.row_actions import Effect, RowAction
from nodus.ui.widgets.tables.row_layout import row_list
from nodus.ui.widgets.tables.transaction_table import CATEGORY

THIS_MONTH = N_("Este mes")
OWN_PART_TEXT = N_("Sin subcategoría")
TOOLTIP_PARTS = 4  # the largest pieces a month's box names
HAS_SUBCATEGORIES_TEXT = N_("Para unirla, primero une o elimina sus subcategorías.")


class CategoryDetailPage(SummaryDetailPage[CategorySummary]):
    """A category from the whole to each piece: its total, this month and its monthly
    average; a bar per month of the same year its total adds up (a click opens that
    month's movements); with subcategories, each bar stacked by them and a card with
    what each one added up to, which opens its page; then its movements. A subcategory
    links to the category it sits in. Amounts read as in Categorías: what was spent, or
    received.

    «Otros» and «Reembolsos» belong to Nodus, so their page only shows them.
    """

    CAPTIONS = (THIS_MONTH, N_("Promedio por mes"))

    transactions_requested = Signal(object)  # TransactionFocus

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__(DetailId.CATEGORY, services, event_bus, theme_manager)
        self.related_line = LinkLine()
        self.chart = StackedBarChart(theme_manager.theme, compact_pesos)
        self.chart.setFixedHeight(Chart.DETAIL_HEIGHT)
        self.chart.clicked.connect(self._month_clicked)
        theme_manager.theme_changed.connect(self.chart.set_theme)
        chart_card = Card()
        card_header(chart_card, _("Mes a mes"))
        chart_card.body.addWidget(self.chart)
        self.parts_card = Card()
        card_header(self.parts_card, _("Por subcategoría"))
        self._part_rows = row_list()
        self.parts_card.body.addLayout(self._part_rows)
        self.part_lines: list[CategoryLine] = []
        at = self.body.indexOf(self.list_view)
        self.body.insertWidget(at, self.related_line)
        self.body.insertWidget(at + 1, chart_card)
        self.body.insertWidget(at + 2, self.parts_card)

    def load_summary(self, item_id: int) -> CategorySummary:
        return self._services.category_report.summary(item_id, self.recent().end)

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
        colors = self._part_colors(summary)
        self._show_months(summary, colors)
        self._show_parts(summary, colors)
        self._show_change(summary)

    def _show_related(self, summary: CategorySummary) -> None:
        """The category a subcategory sits in, as a link to its page; a category's own
        subcategories are in «Por subcategoría», with their amounts."""
        category = summary.category
        related = (
            [self._services.categories.get(category.parent_id)] if category.is_subcategory else []
        )
        label = _("Dentro de:")
        self.related_line.set_links(
            label,
            [
                Link(
                    c.name,
                    DetailId.CATEGORY.open_text,
                    lambda i=c.id: self.record_requested.emit(RecordLink.category(i)),
                )
                for c in related
            ],
        )

    @staticmethod
    def _part_colors(summary: CategorySummary) -> dict[int, str]:
        """The color of each piece, told apart even when a subcategory has its
        category's."""
        pieces = [part.category for part in summary.parts]
        return dict(
            zip((c.id for c in pieces), distinct_colors([c.color for c in pieces]), strict=True)
        )

    def _show_months(self, summary: CategorySummary, colors: dict[int, str]) -> None:
        """A bar per month: in one piece, or stacked by subcategory, the largest at the
        bottom, with the month's largest pieces in its box."""
        self.chart.set_bars(
            [
                self._bar(summary, index, month, total, colors)
                for index, (month, total) in enumerate(summary.months)
            ],
            summary.average.cents if summary.average is not None else None,
        )

    def _bar(
        self,
        summary: CategorySummary,
        index: int,
        month: Month,
        total: Money,
        colors: dict[int, str],
    ) -> StackedBar:
        total_text = amount_text(total, self._hidden)
        if not summary.parts:
            segment = StackSegment(summary.category.id, summary.category.color, total.cents)
            return StackedBar(
                month.short_name, (segment,), format_month(month), (total_text,), month
            )
        pieces = [(part, part.months[index]) for part in summary.parts]
        segments = tuple(
            StackSegment(part.category.id, colors[part.category.id], amount.cents)
            for part, amount in pieces
            if not amount.is_zero
        )
        largest = sorted(
            (piece for piece in pieces if not piece[1].is_zero), key=lambda p: -p[1].cents
        )[:TOOLTIP_PARTS]
        lines = [_("Total {amount}").format(amount=total_text)] + [
            f"{self._part_name(part)} {amount_text(amount, self._hidden)}"
            for part, amount in largest
        ]
        return StackedBar(month.short_name, segments, format_month(month), tuple(lines), month)

    @staticmethod
    def _part_name(part: CategoryPart) -> str:
        return _(OWN_PART_TEXT) if part.is_own else part.category.name

    def _show_parts(self, summary: CategorySummary, colors: dict[int, str]) -> None:
        """What each subcategory added up to in these months, and its share; one opens its
        page. What sits in no subcategory has a row of its own, which opens nothing."""
        self.parts_card.setVisible(bool(summary.children))
        clear_layout(self._part_rows)
        self.part_lines = []
        if not summary.children:
            return
        if not summary.parts:
            self._part_rows.addWidget(muted_label(_("Sin movimientos en estos meses.")))
        for part in summary.parts:
            link = None if part.is_own else RecordLink.category(part.category.id)
            line = CategoryLine(
                colors[part.category.id],
                self._part_name(part),
                movements_text(part.count),
                link,
            )
            line.add(muted_label(percent(part.total, summary.totals.net)))
            amount = amount_label(part.total)
            amount.setText(amount_text(part.total, self._hidden))
            line.add(amount)
            line.opened.connect(self.record_requested)
            self._part_rows.addWidget(line)
            self.part_lines.append(line)

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

    def _month_clicked(self, index: int, key: object) -> None:
        summary = self.summary
        if summary is None:
            return
        month: Month = summary.months[index][0]
        # A subcategory's piece opens its movements; the rest, the whole category's.
        child_ids = {child.id for child in summary.children}
        category_id = key if key in child_ids else summary.category.id
        self.transactions_requested.emit(
            TransactionFocus(Period.of_months(month), category_id=category_id)
        )
