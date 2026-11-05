"""Combo boxes to pick an account or a category."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QWidget

from nodus.models.account import Account
from nodus.services.category_service import CategoryNode
from nodus.ui.widgets.color import color_icon

# Indent that marks a subcategory under its parent in a flat list.
_SUBCATEGORY_INDENT = "      "


class _SelectorComboBox(QComboBox):
    """A combo box whose items carry an id, with an optional first item meaning "any"."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumContentsLength(14)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)

    def current_id(self) -> int | None:
        """The selected item's id; None for the "any" item or an empty list."""
        return self.currentData()

    def select(self, item_id: int | None) -> None:
        """Selects the item with ``item_id``; falls back to the first selectable item."""
        model = self.model()
        index = next(
            (
                i for i in range(self.count())
                if self.itemData(i) == item_id and model.item(i).isEnabled()
            ),
            self._first_selectable(),
        )  # fmt: skip
        self.setCurrentIndex(index)

    def _start(self, all_label: str | None) -> int | None:
        """Clears the items, adds the "any" item if wanted, and returns the previous id."""
        previous = self.current_id()
        self.clear()
        if all_label:
            self.addItem(all_label, None)
        return previous

    def _add_heading(self, text: str) -> None:
        self.addItem(text.upper(), None)
        self.model().item(self.count() - 1).setEnabled(False)

    def _first_selectable(self) -> int:
        model = self.model()
        return next((i for i in range(self.count()) if model.item(i).isEnabled()), -1)


class AccountComboBox(_SelectorComboBox):
    """Lists accounts by name; remembers the selection when the list is reloaded."""

    def set_accounts(self, accounts: list[Account], all_label: str | None = None) -> None:
        self._accounts = {account.id: account for account in accounts}
        self.blockSignals(True)
        previous = self._start(all_label)
        for account in accounts:
            self.addItem(account.name, account.id)
        self.blockSignals(False)
        self.select(previous)

    def current_account(self) -> Account | None:
        account_id = self.current_id()
        return None if account_id is None else self._accounts[account_id]


class CategoryComboBox(_SelectorComboBox):
    """Lists categories as a tree: color dot, parents, then their indented subcategories.

    ``sections`` pairs an optional heading with the tree under it, so one list can show
    expense and income categories apart.
    """

    def set_categories(
        self,
        sections: list[tuple[str | None, list[CategoryNode]]],
        all_label: str | None = None,
    ) -> None:
        self.blockSignals(True)
        previous = self._start(all_label)
        for heading, nodes in sections:
            if heading:
                self._add_heading(heading)
            for node in nodes:
                self.addItem(color_icon(node.category.color), node.category.name, node.category.id)
                for child in node.children:
                    self.addItem(
                        color_icon(child.color), _SUBCATEGORY_INDENT + child.name, child.id
                    )
        self.blockSignals(False)
        self.select(previous)
