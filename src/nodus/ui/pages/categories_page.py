"""Categories section: expense and income categories with their subcategories."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from nodus.models.category import Category
from nodus.models.transaction import TransactionType
from nodus.services.container import Services
from nodus.ui.dialogs.category_dialog import CategoryDialog
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import history_focus
from nodus.ui.pages.page import Page
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.color import ColorDot
from nodus.ui.widgets.row_actions import MoreButton, RowAction, install_context_menu
from nodus.ui.widgets.style import clear_layout

SECTION_TITLES = {TransactionType.EXPENSE: "Gastos", TransactionType.INCOME: "Ingresos"}
SYSTEM_HINT = "Recibe las transacciones de las categorías que se eliminan."


class CategoryRow(QWidget):
    """One category: color, name and the menu of the actions it allows.

    Subcategories are indented. "Otros" cannot change, so its menu only shows its movements.
    """

    transactions_requested = Signal(object)  # Category
    edit_requested = Signal(object)  # Category
    delete_requested = Signal(object)  # Category
    add_subcategory_requested = Signal(object)  # Category

    INDENT = 28

    def __init__(self, category: Category, has_movements: bool = True) -> None:
        super().__init__()
        self.category = category
        self.has_movements = has_movements
        layout = QHBoxLayout(self)
        layout.setContentsMargins(self.INDENT if category.is_subcategory else 0, 4, 0, 4)
        layout.setSpacing(10)
        layout.addWidget(ColorDot(category.color))
        name = QLabel(category.name)
        name.setObjectName("RowTitle")
        layout.addWidget(name)
        if category.is_system:
            tag = QLabel("sistema")
            tag.setObjectName("Tag")
            tag.setToolTip(SYSTEM_HINT)
            layout.addWidget(tag, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch()

        self.more_button = MoreButton(self.actions)
        layout.addWidget(self.more_button)
        install_context_menu(self, self.actions)

    def actions(self) -> list[RowAction]:
        """Its movements, editing and deleting; "Otros" only shows its movements, since it
        cannot change."""
        category = self.category
        result = [
            RowAction(
                "Ver movimientos",
                lambda: self.transactions_requested.emit(category),
                "list",
                enabled=self.has_movements,
            )
        ]
        if category.is_system:
            return result
        result.append(RowAction("Editar", lambda: self.edit_requested.emit(category), "pencil"))
        if not category.is_subcategory:
            result.append(
                RowAction(
                    "Agregar subcategoría",
                    lambda: self.add_subcategory_requested.emit(category),
                    "plus",
                )
            )
        result.append(
            RowAction(
                "Eliminar", lambda: self.delete_requested.emit(category), "trash", destructive=True
            )
        )
        return result


class CategoriesPage(Page):
    """Two cards, expenses then incomes, each listing categories with their subcategories."""

    transactions_requested = Signal(object)  # TransactionFocus

    def __init__(self, services: Services, event_bus: EventBus) -> None:
        super().__init__("Categorías")
        self._services = services
        self._event_bus = event_bus
        self.create_button = self.add_header_button("Nueva categoría", primary=True)
        self.create_button.clicked.connect(lambda: self.open_category_dialog())

        container = QWidget()
        self._sections = QVBoxLayout(container)
        self._sections.setContentsMargins(0, 0, 0, 0)
        self._sections.setSpacing(16)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        self.content_layout.addWidget(scroll)

        event_bus.categories_changed.connect(self.refresh)

    def refresh(self) -> None:
        clear_layout(self._sections)
        for kind, title in SECTION_TITLES.items():
            self._sections.addWidget(self._section(kind, title))
        self._sections.addStretch()

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
        if not confirm(self.window(), "Eliminar categoría", self._delete_warning(category)):
            return
        self._services.categories.delete(category.id)
        self._event_bus.categories_changed.emit()
        self._event_bus.transactions_changed.emit()

    def _section(self, kind: TransactionType, title: str) -> Card:
        card = Card(title)
        for node in self._services.categories.category_tree(kind):
            for category in [node.category, *node.children]:
                card.body.addWidget(self._row(category))
        return card

    def _row(self, category: Category) -> CategoryRow:
        focus = history_focus(self._services, category_id=category.id)
        row = CategoryRow(category, has_movements=focus is not None)
        row.transactions_requested.connect(
            lambda _category: self.transactions_requested.emit(focus)
        )
        row.edit_requested.connect(self.open_category_dialog)
        row.delete_requested.connect(self.delete_category)
        row.add_subcategory_requested.connect(
            lambda parent: self.open_category_dialog(kind=parent.kind, parent_id=parent.id)
        )
        return row

    def _delete_warning(self, category: Category) -> str:
        has_children = any(
            node.category.id == category.id and node.children
            for node in self._services.categories.category_tree(category.kind)
        )
        subject = f"«{category.name}»" + (" y sus subcategorías" if has_children else "")
        count = self._services.categories.transaction_count(category.id)
        if count == 0:
            consequence = "No tiene transacciones."
        elif count == 1:
            consequence = "Su única transacción pasa a «Otros»."
        else:
            consequence = f"Sus {count} transacciones pasan a «Otros»."
        return f"Se va a eliminar {subject}. {consequence}"
