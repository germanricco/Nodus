"""Dialog to set a category's monthly budget, or to change it."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget

from nodus.models.category import Category
from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.period import Month, format_month
from nodus.services.budget_service import SUGGESTION_MONTHS
from nodus.services.category_service import CategoryNode
from nodus.services.container import Services
from nodus.services.errors import ValidationError
from nodus.ui.dialogs.form_dialog import FormDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.widgets.amount_input import AmountInput
from nodus.ui.widgets.selectors import CategoryComboBox


class BudgetDialog(FormDialog):
    """Sets the limit of a category from ``month`` on.

    Without ``category`` it offers the top-level expense categories that have no budget
    yet; with it, the category is fixed and its limit is set or changed. The amount comes
    filled in with the current limit, or else with the average spending of the last
    months, as a starting point.
    """

    def __init__(
        self,
        services: Services,
        event_bus: EventBus,
        month: Month,
        category: Category | None = None,
        parent: QWidget | None = None,
    ) -> None:
        limits = services.budgets.limits_on(month)
        has_limit = category is not None and category.id in limits
        super().__init__("Cambiar límite" if has_limit else "Nuevo presupuesto", parent)
        self._services = services
        self._event_bus = event_bus
        self._month = month

        self.category_input = CategoryComboBox()
        candidates = [category] if category else self._free_categories(limits)
        self.category_input.set_categories([(None, [CategoryNode(c, []) for c in candidates])])
        self.category_input.setEnabled(category is None)
        self.amount_input = AmountInput(Currency.ARS)
        self.suggestion_hint = QLabel()
        self.suggestion_hint.setObjectName("FieldHint")
        self.suggestion_hint.setWordWrap(True)
        scope_hint = QLabel(
            f"Rige desde {format_month(month).lower()} en adelante; "
            "los meses anteriores conservan su límite."
        )
        scope_hint.setObjectName("FieldHint")
        scope_hint.setWordWrap(True)

        self.form.addRow("Categoría", self.category_input)
        self.form.addRow("Límite mensual", self.amount_input)
        self.form.addRow("", self.suggestion_hint)
        self.form.addRow("", scope_hint)

        self.category_input.currentIndexChanged.connect(self._show_suggestion)
        if category:
            self.category_input.select(category.id)
        self._show_suggestion()
        if has_limit:
            self.amount_input.set_money(limits[category.id])

    def _free_categories(self, limits: dict[int, Money]) -> list[Category]:
        """Top-level expense categories without a budget in the month."""
        return [c for c in self._services.budgets.categories() if c.id not in limits]

    def _show_suggestion(self) -> None:
        category_id = self.category_input.current_id()
        suggestion = (
            self._services.budgets.suggestion(category_id, self._month)
            if category_id is not None
            else None
        )
        self.suggestion_hint.setVisible(suggestion is not None)
        if suggestion is not None:
            self.suggestion_hint.setText(
                f"Promedio de los últimos {SUGGESTION_MONTHS} meses: {suggestion.format()}"
            )
            self.amount_input.set_money(suggestion)

    def save(self) -> None:
        category_id = self.category_input.current_id()
        if category_id is None:
            raise ValidationError("Elige una categoría.")
        self._services.budgets.set_limit(category_id, self._month, self.amount_input.money())
        self._event_bus.budgets_changed.emit()
