"""Categories section: what each expense and income category added up to in a period,
with its subcategories, and the actions to manage them."""

from __future__ import annotations

import dataclasses
from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from nodus.i18n import N_, _, ngettext
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
from nodus.ui.actions.categories import delete_categories
from nodus.ui.dialogs.category_dialog import CategoryDialog, MergeCategoryDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import PageId, history_focus
from nodus.ui.pages.base.page import Page
from nodus.ui.period_selector import PeriodSelector
from nodus.ui.shortcuts import CLEAR_SELECTION, DELETE_ROWS
from nodus.ui.text.formatting import rate_text
from nodus.ui.text.labels import unconverted_note
from nodus.ui.theme.design import Layout, Space
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card, card_title
from nodus.ui.widgets.charts.chart_base import shown_fractions
from nodus.ui.widgets.charts.share_bar import ShareBar
from nodus.ui.widgets.color_dot import ColorDot
from nodus.ui.widgets.empty_state import EmptyState
from nodus.ui.widgets.money_label import amount_text
from nodus.ui.widgets.style import RIGHT_ALIGNED, clear_layout, hint_label, muted_label, separator
from nodus.ui.widgets.tables.fold_button import FoldButton
from nodus.ui.widgets.tables.row_actions import (
    Effect,
    MoreButton,
    RowAction,
    install_row_actions,
)
from nodus.ui.widgets.tables.selection_bar import SelectionBar
from nodus.ui.widgets.tables.table import DELETE_KEY_HINT

SECTION_TITLES = {TransactionType.EXPENSE: N_("Gastos"), TransactionType.INCOME: N_("Ingresos")}
NOTHING_TEXTS = {
    TransactionType.EXPENSE: N_("Sin gastos"),
    TransactionType.INCOME: N_("Sin ingresos"),
}
SYSTEM_HINT = N_("Recibe las transacciones de las categorías que se eliminan.")
REFUNDS_HINT = N_("Sus ingresos se pueden vincular al gasto que devuelven, con «Reembolso de».")
NO_MATCHES_TEXT = N_("Ninguna categoría coincide con la búsqueda.")
CANNOT_MERGE_TEXT = N_(
    "Se unen categorías del mismo tipo, sin subcategorías y que no sean de sistema."
)


class CategoryRow(QWidget):
    """One category in the period: color and name, how much of its kind it weighs (bar and
    percent), the amount and the menu of what it allows. Budgets stay in Presupuestos.

    A check box at the start chooses it, to merge or delete several at once. A category
    with subcategories has an arrow after it that folds them; folded, it says how many it
    holds, and its amount still adds them up. Subcategories are indented after it. A system
    category («Otros», «Reembolsos») cannot change, so it has no box and its menu only opens
    it and shows its movements. The box, the fold, bar, percent and amount keep their place
    on every row, so they line up down the list.
    """

    chosen_changed = Signal(object, bool)  # Category, chosen
    fold_toggled = Signal(object, bool)  # Category, folded

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
        chosen: bool = False,
        folded: bool = False,
    ) -> None:
        """``hidden`` masks the amount; ``has_movements`` says whether the category has
        any at all, in any period; ``start`` is where its bar begins (``ProgressStrip``);
        ``can_merge`` whether it can join another (``CategoryService.can_merge``);
        ``chosen`` whether its box starts checked; ``folded`` whether its subcategories
        start hidden."""
        super().__init__()
        self.figures = figures
        self.category = category = figures.category
        self.has_movements = has_movements
        self.can_merge = can_merge
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Space.S, Space.XS, Space.S, Space.XS)
        layout.setSpacing(Space.S)
        self.check_box = QCheckBox()
        self.check_box.setAccessibleName(_("Elegir «{name}»").format(name=category.name))
        self.check_box.setChecked(chosen)
        self.check_box.toggled.connect(lambda on: self.chosen_changed.emit(category, on))
        keep_place(self.check_box)
        layout.addWidget(self.check_box)
        subcategories = len(figures.children)
        self.fold_button = FoldButton(category.name, folded)
        self.fold_button.fold_toggled.connect(lambda on: self.fold_toggled.emit(category, on))
        keep_place(self.fold_button)
        layout.addWidget(self.fold_button)
        if category.is_subcategory:
            layout.addSpacing(self.INDENT)
        layout.addWidget(ColorDot(category.color))
        name = QLabel(category.name)
        name.setObjectName("RowTitle")
        layout.addWidget(name)
        if category.is_fixed:
            tag = QLabel(_("sistema"))
            tag.setObjectName("Tag")
            tag.setToolTip(_(SYSTEM_HINT) if category.is_system else _(REFUNDS_HINT))
            layout.addWidget(tag, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.subcategories_label = muted_label(
            ngettext("{count} subcategoría", "{count} subcategorías", subcategories).format(
                count=subcategories
            )
        )
        layout.addWidget(self.subcategories_label)
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
            keep_place(widget)
        layout.addWidget(self.bar, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.percent_label)
        layout.addWidget(self.amount_label)
        # Hidden once in the row: shown before it has a parent, they would flash as windows.
        self.bar.setHidden(not shows_share)
        self.check_box.setHidden(category.is_fixed)
        self.fold_button.setHidden(not subcategories)
        self.subcategories_label.setHidden(not (subcategories and folded))

        self.more_button = MoreButton(self.actions)
        layout.addWidget(self.more_button)
        # Its box chooses it, so it opens with a double click, as the lists that are tables.
        install_row_actions(self, self.actions)

    def set_folded(self, folded: bool) -> None:
        self.fold_button.set_folded(folded)
        self.subcategories_label.setVisible(folded)

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
        """Its page (what a double click opens), its movements, and editing, merging and
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

    The period starts on the current month. With two or more chosen, the header becomes
    the selection bar, to merge or delete them together; Supr deletes the chosen ones and
    Esc lets them go.
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
        self._children: dict[int, list[CategoryRow]] = {}  # by the id of their category
        self._chosen: dict[int, Category] = {}  # by id, in the order they were chosen

        self.period_selector = PeriodSelector(Period.of_months(Month.of(date.today())))
        self.add_header_widget(self.period_selector)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(_("Buscar categoría…"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(Layout.SEARCH_WIDTH)
        self.add_header_widget(self.search_input)
        self.create_button = self.add_header_button(_("Agregar categoría"), primary=True)
        self.create_button.clicked.connect(lambda: self.open_category_dialog())

        self.selection_bar = SelectionBar(_("seleccionadas"))
        self.merge_button = self.selection_bar.add_action(_("Unir…"), self.merge_chosen)
        self.delete_button = self.selection_bar.add_action(
            _("Eliminar"), self.delete_chosen, destructive=True
        )
        self.delete_button.setToolTip(_(DELETE_KEY_HINT))
        self.selection_bar.cleared.connect(self.clear_chosen)
        self.set_selection_bar(self.selection_bar)

        self._sections = self.scrolling_body()

        self.period_selector.period_changed.connect(lambda _period: self.refresh())
        self.search_input.textChanged.connect(lambda _text: self._show())

    def refresh(self) -> None:
        self._report = self._services.category_report.report(self.period_selector.period())
        # A chosen category that was deleted or merged is no longer chosen.
        existing = {c.id: c for c in self._services.categories.list_categories()}
        self._chosen = {i: existing[i] for i in self._chosen if i in existing}
        self._show()
        self._update_selection()

    @property
    def chosen(self) -> list[Category]:
        return list(self._chosen.values())

    def clear_chosen(self) -> None:
        self._chosen.clear()
        for row in self._rows.values():
            row.check_box.setChecked(False)
        self._update_selection()

    def merge_chosen(self) -> None:
        if not self._services.categories.can_merge_together(list(self._chosen)):
            return
        if MergeCategoryDialog(
            self._services, self._event_bus, self.chosen, parent=self.window()
        ).exec():
            self.clear_chosen()

    def delete_chosen(self) -> None:
        if self._chosen and delete_categories(
            self.window(), self._services, self._event_bus, self.chosen
        ):
            self.clear_chosen()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        # Reaches the page when no field used it, as on the lists that are tables.
        if CLEAR_SELECTION.matches(event) and self._chosen:
            self.clear_chosen()
            return
        if DELETE_ROWS.matches(event) and self._chosen:
            self.delete_chosen()
            return
        super().keyPressEvent(event)

    def _choose(self, category: Category, chosen: bool) -> None:
        if chosen:
            self._chosen[category.id] = category
        else:
            self._chosen.pop(category.id, None)
        self._update_selection()

    def _update_selection(self) -> None:
        """With two or more chosen, the header becomes the selection bar."""
        count = len(self._chosen)
        self.show_selection_bar(count > 1)
        if count < 2:
            return
        self.selection_bar.set_count(count)
        together = self._services.categories.can_merge_together(list(self._chosen))
        self.merge_button.setEnabled(together)
        self.merge_button.setToolTip(
            _("Deja una sola y le pasa los movimientos de las demás")
            if together
            else _(CANNOT_MERGE_TEXT)
        )

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
        delete_categories(self.window(), self._services, self._event_bus, [category])

    def _show(self) -> None:
        """The report's sections, narrowed to the categories the search matches."""
        report = self._report
        if report is None:
            return
        starts = shown_fractions({key: row.bar for key, row in self._rows.items()})
        clear_layout(self._sections)
        self._rows = {}
        self._children = {}
        hidden = self._services.settings.amounts_hidden()
        wanted = normalize_name(self.search_input.text())
        for section in report.sections:
            categories = _matching(section.categories, wanted)
            if categories:
                self._sections.addWidget(
                    self._section(section, categories, hidden, starts, bool(wanted))
                )
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
        searching: bool,
    ) -> Card:
        """A card with its total under its title, as the caption and value of a figure
        tile, then a group per category: the category and its subcategories, which it may
        fold. A thin line goes between groups, never inside one, so each category reads as
        one block with what it holds."""
        card = Card()
        heading = QVBoxLayout()
        heading.setSpacing(Space.XXS)
        heading.addWidget(card_title(_(SECTION_TITLES[section.kind])))
        total = QLabel(amount_text(section.total, hidden))
        total.setObjectName("StatValue")
        total.setAccessibleName(
            _("Total de {kind}: {amount}").format(
                kind=_(SECTION_TITLES[section.kind]).lower(), amount=total.text()
            )
        )
        heading.addWidget(total)
        card.body.addLayout(heading)
        card.body.addSpacing(Space.S)
        # A search shows the subcategories it found, even in a folded category.
        folded_ids = set() if searching else self._services.settings.folded_categories()
        for position, figures in enumerate(categories):
            if position:
                card.body.addWidget(separator())
            group = QWidget()
            rows = QVBoxLayout(group)
            rows.setContentsMargins(0, 0, 0, 0)
            rows.setSpacing(0)
            folded = figures.category.id in folded_ids
            rows.addWidget(self._row(figures, hidden, starts, folded))
            children = [self._row(child, hidden, starts) for child in figures.children]
            for child in children:
                rows.addWidget(child)
                child.setHidden(folded)
            self._children[figures.category.id] = children
            card.body.addWidget(group)
        return card

    def _fold(self, category: Category, folded: bool) -> None:
        """Folds or unfolds the subcategories of ``category``, and remembers it."""
        folded_ids = self._services.settings.folded_categories()
        if folded:
            folded_ids.add(category.id)
        else:
            folded_ids.discard(category.id)
        self._services.settings.set_folded_categories(folded_ids)
        self._rows[category.id].set_folded(folded)
        for child in self._children.get(category.id, []):
            child.setHidden(folded)

    def _row(
        self,
        figures: CategoryFigures,
        hidden: bool,
        starts: dict[int, float],
        folded: bool = False,
    ) -> CategoryRow:
        category = figures.category
        focus = history_focus(self._services, category_id=category.id)
        row = CategoryRow(
            figures,
            self._theme_manager.theme,
            hidden,
            has_movements=focus is not None,
            start=starts.get(category.id),
            can_merge=self._services.categories.can_merge(category.id),
            chosen=category.id in self._chosen,
            folded=folded,
        )
        row.chosen_changed.connect(self._choose)
        row.fold_toggled.connect(self._fold)
        self._rows[category.id] = row
        row.transactions_requested.connect(
            lambda _category: self.transactions_requested.emit(focus)
        )
        row.open_requested.connect(lambda c: self.detail_requested.emit(c.id))
        row.edit_requested.connect(self.open_category_dialog)
        row.merge_requested.connect(
            lambda c: MergeCategoryDialog(
                self._services, self._event_bus, [c], parent=self.window()
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


def keep_place(widget: QWidget) -> None:
    """``widget`` keeps its room while hidden, so the columns of every row line up."""
    policy = widget.sizePolicy()
    policy.setRetainSizeWhenHidden(True)
    widget.setSizePolicy(policy)
