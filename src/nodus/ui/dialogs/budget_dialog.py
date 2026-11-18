"""Dialog to set a category's monthly budget, or to change it."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from nodus.i18n import _, ngettext
from nodus.models.category import Category
from nodus.models.currency import HOME_CURRENCY
from nodus.models.money import Money
from nodus.models.period import Month, format_month_in_sentence
from nodus.services.classification.category_service import CategoryNode
from nodus.services.container import Services
from nodus.services.planning.budget_service import BudgetSuggestion
from nodus.ui.dialogs.form_dialog import (
    CATEGORY_PLACEHOLDER,
    CHOOSE_CATEGORY,
    SAVE_CHANGES,
    TYPE_AMOUNT,
    FormDialog,
)
from nodus.ui.event_bus import EventBus
from nodus.ui.widgets.inputs.amount_input import AmountInput
from nodus.ui.widgets.inputs.selectors import CategoryComboBox
from nodus.ui.widgets.style import hint_label


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
        super().__init__(
            _("Cambiar límite") if has_limit else _("Nuevo presupuesto"),
            parent,
            _(SAVE_CHANGES) if has_limit else _("Agregar presupuesto"),
        )
        self._services = services
        self._event_bus = event_bus
        self._month = month

        self.category_input = CategoryComboBox()
        if category is None:
            self.category_input.set_placeholder(_(CATEGORY_PLACEHOLDER))
        candidates = [category] if category else self._free_categories(limits)
        self.category_input.set_categories([(None, [CategoryNode(c, []) for c in candidates])])
        self.category_input.setEnabled(category is None)
        self.amount_input = AmountInput(HOME_CURRENCY)
        self.suggestion_hint = hint_label()
        self.suggestion_hint.setWordWrap(True)
        scope_hint = hint_label(
            _("Rige desde {month} en adelante; los meses anteriores conservan su límite.").format(
                month=format_month_in_sentence(month)
            )
        )
        scope_hint.setWordWrap(True)

        self.form.addRow(_("Categoría"), self.category_input)
        self.bind_field(self.category_input, "category_id")
        self.bind_field(self.amount_input, "limit")
        self.form.addRow(_("Límite mensual"), self.amount_input)
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
            self.suggestion_hint.setText(suggestion_text(suggestion))
            self.amount_input.set_money(suggestion.amount)

    def missing(self) -> dict[QWidget, str]:
        return self.required(
            (self.category_input, _(CHOOSE_CATEGORY)), (self.amount_input, _(TYPE_AMOUNT))
        )

    def save(self) -> None:
        category_id = self.category_input.current_id()
        assert category_id is not None  # ``missing`` asks for it first
        self._services.budgets.set_limit(category_id, self._month, self.amount_input.money())
        self._event_bus.budgets_changed.emit()


def suggestion_text(suggestion: BudgetSuggestion) -> str:
    """ "Promedio de los últimos 3 meses: $ 350.000,00", or, after a single month of use,
    "Lo gastado el mes pasado: $ 90.000,00"."""
    amount = suggestion.amount.format()
    if suggestion.months == 1:
        return _("Lo gastado el mes pasado: {amount}").format(amount=amount)
    return ngettext(
        "Promedio del último {count} mes: {amount}",
        "Promedio de los últimos {count} meses: {amount}",
        suggestion.months,
    ).format(count=suggestion.months, amount=amount)
