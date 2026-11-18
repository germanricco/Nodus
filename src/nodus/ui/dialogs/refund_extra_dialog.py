"""A refund that brings back more than was left of its expense: the refund keeps what was
left, and the rest is saved apart, as an income of the category the user chooses."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget

from nodus.i18n import _
from nodus.models.money import Money
from nodus.models.transaction import TransactionType
from nodus.services.container import Services
from nodus.services.transactions.transaction_service import TransactionDraft
from nodus.ui.dialogs.form_dialog import CHOOSE_CATEGORY, FormDialog
from nodus.ui.widgets.inputs.selectors import CategoryComboBox


class RefundExtraDialog(FormDialog):
    """Offers to split ``draft``, a refund ``excess`` over what was left of its expense,
    into the refund and an income for the rest; «Otros» is chosen first, since the rest
    pays nothing back. ``transaction_id`` is the refund being edited, if any."""

    def __init__(
        self,
        services: Services,
        draft: TransactionDraft,
        excess: Money,
        transaction_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(_("Te devolvieron de más"), parent, _("Anotar los dos"))
        self._services = services
        self._draft = draft
        self._transaction_id = transaction_id

        left = draft.amount - excess
        message = QLabel(
            _(
                "Te devolvieron {amount} y de ese gasto quedaban {left} por reembolsar."
                " Se anota {left} como reembolso y {excess} como un ingreso aparte."
            ).format(amount=draft.amount.format(), left=left.format(), excess=excess.format())
        )
        message.setWordWrap(True)
        self.form.addRow(message)

        income = TransactionType.INCOME
        self.category_input = CategoryComboBox()
        self.category_input.set_categories([(None, services.categories.category_tree(income))])
        others = next(c for c in services.categories.list_categories(income) if c.is_system)
        self.category_input.select(others.id)
        self.form.addRow(_("Categoría de lo que sobra"), self.category_input)
        self.bind_field(self.category_input, "category_id")

    def missing(self) -> dict[QWidget, str]:
        return self.required((self.category_input, _(CHOOSE_CATEGORY)))

    def save(self) -> None:
        category_id = self.category_input.current_id()
        assert category_id is not None  # ``missing`` asks for it first
        self._services.transactions.save_refund_with_extra(
            self._draft, category_id, self._transaction_id
        )
