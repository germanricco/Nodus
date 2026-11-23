"""Categories section: what each expense and income category added up to in a period,
with its subcategories, and the actions to manage them."""

from __future__ import annotations

import dataclasses
from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QWidget

from nodus.i18n import N_, _
from nodus.models.category import Category
from nodus.models.names import normalize_name
from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
from nodus.services.container import Services
from nodus.services.reports.category_report_service import (
    CategoryFigures,
    CategoryReport,
    CategorySection,
)
from nodus.ui.actions.categories import delete_category
from nodus.ui.dialogs.category_dialog import CategoryDialog, MergeCategoryDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import PageId, history_focus
from nodus.ui.pages.base.page import Page
from nodus.ui.period_selector import PeriodSelector
from nodus.ui.text.formatting import rate_text
from nodus.ui.text.labels import unconverted_note
from nodus.ui.theme.design import Layout, Space
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card, card_header
from nodus.ui.widgets.charts.chart_base import shown_fractions
from nodus.ui.widgets.charts.share_bar import ShareBar
from nodus.ui.widgets.color_dot import ColorDot
from nodus.ui.widgets.empty_state import EmptyState
from nodus.ui.widgets.money_label import amount_text
from nodus.ui.widgets.style import RIGHT_ALIGNED, clear_layout, hint_label, muted_label
from nodus.ui.widgets.tables.row_actions import Effect, MoreButton, RowAction, install_row_actions

SECTION_TITLES = {TransactionType.EXPENSE: N_("Gastos"), TransactionType.INCOME: N_("Ingresos")}
NOTHING_TEXTS = {
    TransactionType.EXPENSE: N_("Sin gastos"),
    TransactionType.INCOME: N_("Sin ingresos"),
}
SYSTEM_HINT = N_("Recibe las transacciones de las categorías que se eliminan.")
REFUNDS_HINT = N_("Sus ingresos se pueden vincular al gasto que devuelven, con «Reembolso de».")
NO_MATCHES_TEXT = N_("Ninguna categoría coincide con la búsqueda.")


class CategoryRow(QWidget):
    """One category in the period: color and name, how much of its kind it weighs (bar and
    percent), the amount and the menu of what it allows. Budgets stay in Presupuestos.

    Subcategories are indented. A system category («Otros», «Reembolsos») cannot change,
    so its menu only shows its movements. The bar, percent and amount keep their width on
    every row, so they line up down the list.
    """

    open_requested = Signal(object)  # Category
    transactions_requested = Signal(object)  # Category
    edit_requested = Signal(object)  # Category
    merge_requested = Signal(object)  # Category
    delete_requested = Signal(object)  # Category
    add_subcategory_requested = Signal(object)  # Category

    INDENT = Layout.TREE_INDENT

    def __init__(
        self,
        figures: CategoryFigures,
        theme: Theme,
        hidden: bool = False,
        has_movements: bool = True,
        start: float | None = None,
        can_merge: bool = False,
    ) -> None:
        """``hidden`` masks the amount; ``has_movements`` says whether the category has
        any at all, in any period; ``start`` is where its bar begins (``ProgressStrip``);
        ``can_merge`` whether it can join another (``CategoryService.can_merge``)."""
        super().__init__()
        self.figures = figures
        self.category = category = figures.category
        self.has_movements = has_movements
        self.can_merge = can_merge
        layout = QHBoxLayout(self)
        indent = self.INDENT if category.is_subcategory else 0
        layout.setContentsMargins(Space.S + indent, Space.XS, Space.S, Space.XS)
        layout.setSpacing(Space.S)
        layout.addWidget(ColorDot(category.color))
        name = QLabel(category.name)
        name.setObjectName("RowTitle")
        layout.addWidget(name)
        if category.is_fixed:
            tag = QLabel(_("sistema"))
            tag.setObjectName("Tag")
            tag.setToolTip(_(SYSTEM_HINT) if category.is_system else _(REFUNDS_HINT))
            layout.addWidget(tag, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch()

        # A category whose refunds outweigh its spending has nothing to weigh.
        shows_share = figures.total.cents > 0 and figures.share is not None
        self.bar = ShareBar(theme, max(0.0, figures.share or 0.0), category.color, start)
        self.bar.setFixedWidth(Layout.SHARE_BAR_WIDTH)
        self.percent_label = muted_label(rate_text(figures.share) if shows_share else "")
        self.percent_label.setFixedWidth(Layout.SHARE_PERCENT_WIDTH)
        self.percent_label.setAlignment(RIGHT_ALIGNED)
        self.amount_label = self._amount(figures, hidden)
        for widget in (self.bar, self.percent_label):
            policy = widget.sizePolicy()
            policy.setRetainSizeWhenHidden(True)
            widget.setSizePolicy(policy)
        layout.addWidget(self.bar, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.percent_label)
        layout.addWidget(self.amount_label)
        # Hidden once in the row: shown before it has a parent, it would flash as a window.
        self.bar.setHidden(not shows_share)

        self.more_button = MoreButton(self.actions)
        layout.addWidget(self.more_button)
        install_row_actions(self, self.actions, open_on_click=_("Abrir la categoría"))

    @staticmethod
    def _amount(figures: CategoryFigures, hidden: bool) -> QLabel:
        """The amount, or «Sin gastos» in gray when nothing moved in the period."""
        if figures.count:
            label = QLabel(amount_text(figures.total, hidden))
        else:
            label = muted_label(_(NOTHING_TEXTS[figures.category.kind]))
        label.setFixedWidth(Layout.SHARE_AMOUNT_WIDTH)
        label.setAlignment(RIGHT_ALIGNED)
        return label

    def actions(self) -> list[RowAction]:
        """Its page (what a click opens), its movements, and editing, merging and
        deleting it; a system category («Otros», «Reembolsos») cannot change, so it only
        opens."""
        category = self.category
        result = [
            RowAction(
                _("Abrir"),
                lambda: self.open_requested.emit(category),
                default=True,
                effect=Effect.OPEN,
            ),
            RowAction(
                _("Ver movimientos"),
                lambda: self.transactions_requested.emit(category),
                "list",
                enabled=self.has_movements,
                effect=Effect.OPEN,
            ),
        ]
        if category.is_fixed:
            return result
        result.append(
            RowAction(
                _("Editar"),
                lambda: self.edit_requested.emit(category),
                "pencil",
                effect=Effect.OPEN,
            )
        )
        if not category.is_subcategory:
            result.append(
                RowAction(
                    _("Agregar subcategoría"),
                    lambda: self.add_subcategory_requested.emit(category),
                    "plus",
                    effect=Effect.OPEN,
                )
            )
        result += [
            RowAction(
                _("Unir con…"),
                lambda: self.merge_requested.emit(category),
                "merge",
                enabled=self.can_merge,
                effect=Effect.OPEN,
            ),
            RowAction(
                _("Eliminar"),
                lambda: self.delete_requested.emit(category),
                "trash",
                destructive=True,
                effect=Effect.CONFIRMED,
            ),
        ]
        return result


class CategoriesPage(Page):
    """Two cards, expenses then incomes, each with its total for the period and its
    categories from the largest down, subcategories under their parent. A search narrows
    them by name.

    The period starts on the current month.
    """

    transactions_requested = Signal(object)  # TransactionFocus
    detail_requested = Signal(int)  # category id

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__(PageId.CATEGORIES.label)
        self._services = services
        self._event_bus = event_bus
        self._theme_manager = theme_manager
        self._report: CategoryReport | None = None
        self._rows: dict[int, CategoryRow] = {}

        self.period_selector = PeriodSelector(Period.of_months(Month.of(date.today())))
        self.add_header_widget(self.period_selector)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(_("Buscar categoría…"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(Layout.SEARCH_WIDTH)
        self.add_header_widget(self.search_input)
        self.create_button = self.add_header_button(_("Agregar categoría"), primary=True)
        self.create_button.clicked.connect(lambda: self.open_category_dialog())

        self._sections = self.scrolling_body()

        self.period_selector.period_changed.connect(lambda _period: self.refresh())
        self.search_input.textChanged.connect(lambda _text: self._show())

    def refresh(self) -> None:
        self._report = self._services.category_report.report(self.period_selector.period())
        self._show()

    def open_category_dialog(
        self,
        category: Category | None = None,
        kind: TransactionType = TransactionType.EXPENSE,
        parent_id: int | None = None,
    ) -> None:
        CategoryDialog(
            self._services, self._event_bus, category, kind, parent_id, parent=self.window()
        ).exec()

    def delete_category(self, category: Category) -> None:
        delete_category(self.window(), self._services, self._event_bus, category)

    def _show(self) -> None:
        """The report's sections, narrowed to the categories the search matches."""
        report = self._report
        if report is None:
            return
        starts = shown_fractions({key: row.bar for key, row in self._rows.items()})
        clear_layout(self._sections)
        self._rows = {}
        hidden = self._services.settings.amounts_hidden()
        wanted = normalize_name(self.search_input.text())
        for section in report.sections:
            categories = _matching(section.categories, wanted)
            if categories:
                self._sections.addWidget(self._section(section, categories, hidden, starts))
        if not self._rows:
            empty = EmptyState()
            empty.set_message(_(NO_MATCHES_TEXT), _("Borrar búsqueda"), self.search_input.clear)
            self._sections.addWidget(empty)
        if report.unconverted:
            self._sections.addWidget(hint_label(unconverted_note(report.unconverted)))
        self._sections.addStretch()

    def _section(
        self,
        section: CategorySection,
        categories: list[CategoryFigures],
        hidden: bool,
        starts: dict[int, float],
    ) -> Card:
        card = Card()
        header = card_header(card, _(SECTION_TITLES[section.kind]))
        total = QLabel(amount_text(section.total, hidden))
        total.setObjectName("RowTitle")
        header.addWidget(total)
        for figures in categories:
            card.body.addWidget(self._row(figures, hidden, starts))
            for child in figures.children:
                card.body.addWidget(self._row(child, hidden, starts))
        return card

    def _row(self, figures: CategoryFigures, hidden: bool, starts: dict[int, float]) -> CategoryRow:
        category = figures.category
        focus = history_focus(self._services, category_id=category.id)
        row = CategoryRow(
            figures,
            self._theme_manager.theme,
            hidden,
            has_movements=focus is not None,
            start=starts.get(category.id),
            can_merge=self._services.categories.can_merge(category.id),
        )
        self._rows[category.id] = row
        row.transactions_requested.connect(
            lambda _category: self.transactions_requested.emit(focus)
        )
        row.open_requested.connect(lambda c: self.detail_requested.emit(c.id))
        row.edit_requested.connect(self.open_category_dialog)
        row.merge_requested.connect(
            lambda c: MergeCategoryDialog(
                self._services, self._event_bus, c, parent=self.window()
            ).exec()
        )
        row.delete_requested.connect(self.delete_category)
        row.add_subcategory_requested.connect(
            lambda parent: self.open_category_dialog(kind=parent.kind, parent_id=parent.id)
        )
        return row


def _matching(categories: list[CategoryFigures], wanted: str) -> list[CategoryFigures]:
    """The categories whose name contains ``wanted``, ignoring case and accents. A parent
    that matches keeps all its subcategories; one that doesn't stays only to hold the
    subcategories that do."""
    if not wanted:
        return categories
    kept = []
    for figures in categories:
        if wanted in normalize_name(figures.category.name):
            kept.append(figures)
            continue
        children = tuple(c for c in figures.children if wanted in normalize_name(c.category.name))
        if children:
            kept.append(dataclasses.replace(figures, children=children))
    return kept
