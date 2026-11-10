"""Linking an income to the expense it pays back: the field in the transaction dialog and
the dialog that picks the expense."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLayout, QLineEdit, QPushButton, QWidget

from nodus.models.period import Period, format_date
from nodus.models.transaction import Transaction, TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.container import Services
from nodus.ui.dialogs.form_dialog import FormDialog
from nodus.ui.theme.design import Layout
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.transaction_list import TransactionListBuilder
from nodus.ui.widgets.input_error import InputError
from nodus.ui.widgets.period_selector import PeriodSelector
from nodus.ui.widgets.table import record_table
from nodus.ui.widgets.transaction_table import DESCRIPTION, TAGS, TransactionTableModel

# The expenses offered first: refunds usually come within a few months.
CANDIDATE_MONTHS = 6


def is_fully_refunded(expense: Transaction, refunded: dict[int, list]) -> bool:
    """Whether the refunds in the expense's currency already cover all of it."""
    same_currency = [
        money.cents for money in refunded.get(expense.id, [])
        if money.currency is expense.amount.currency
    ]  # fmt: skip
    return sum(same_currency) >= expense.amount.cents


class RefundPickerDialog(FormDialog):
    """Lists the expenses of a period that can still be refunded, newest first, with a
    search, and returns the chosen one in ``chosen``. ``linked_id`` is the expense the
    refund already pays back, offered even when fully refunded."""

    def __init__(
        self,
        services: Services,
        theme_manager: ThemeManager,
        linked_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Elegir el gasto que se reembolsa", parent, "Vincular")
        # A list, not a form: it opens large and the user can resize it.
        self.layout().setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
        self.setMinimumSize(*Layout.PICKER_MIN_SIZE)
        self._services = services
        self._linked_id = linked_id
        self._builder = TransactionListBuilder(services)
        self.chosen: Transaction | None = None

        self.period_selector = PeriodSelector(Period.last_months(CANDIDATE_MONTHS, date.today()))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar…")
        self.search_input.setToolTip("Busca en la nota, el beneficiario y las etiquetas")
        self.search_input.setClearButtonEnabled(True)
        row = QHBoxLayout()
        row.addWidget(self.period_selector)
        row.addWidget(self.search_input, stretch=1)
        self.form.addRow(row)

        self.model = TransactionTableModel(theme_manager.theme)
        self.table = record_table(self.model, DESCRIPTION)
        self.table.hideColumn(TAGS)  # the picker only needs to recognize the expense
        self.table.doubleClicked.connect(lambda _index: self._on_save())
        self.empty_label = QLabel("Sin gastos para reembolsar en este período")
        self.empty_label.setObjectName("FieldHint")
        self.form.addRow(self.table)
        self.form.addRow(self.empty_label)

        self.period_selector.period_changed.connect(self.reload)
        self.search_input.textChanged.connect(self.reload)
        self.reload()

    def reload(self) -> None:
        period = self.period_selector.period()
        expenses = self._services.transactions.list_transactions(
            TransactionFilter(
                start=period.start,
                end=period.end,
                type=TransactionType.EXPENSE,
                is_transfer=False,
                text=self.search_input.text().strip() or None,
            )
        )
        refunded = self._services.transactions.refund_totals()
        candidates = [
            expense
            for expense in expenses
            if expense.id == self._linked_id or not is_fully_refunded(expense, refunded)
        ]
        self.model.set_items(self._builder.build(candidates))
        self.table.setVisible(bool(candidates))
        self.empty_label.setVisible(not candidates)

    def save(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            raise InputError("Elige el gasto que se reembolsa.", self.table)
        self.chosen = self.model.item(rows[0].row()).transaction


class RefundField(QWidget):
    """The expense an income pays back: a button to choose it, or a summary of it with a
    button to unlink it. ``refund_id`` is the income being edited, whose own amount does
    not count against what is left of the expense."""

    changed = Signal()

    def __init__(
        self,
        services: Services,
        theme_manager: ThemeManager,
        refund_id: int | None = None,
    ) -> None:
        super().__init__()
        self._services = services
        self._theme_manager = theme_manager
        self._refund_id = refund_id
        self._expense: Transaction | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.link_button = QPushButton("Vincular a un gasto…")
        self.link_button.setObjectName("SecondaryButton")
        self.link_button.setToolTip("Si este ingreso devuelve un gasto, lo resta de lo gastado")
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.unlink_button = QPushButton("Quitar")
        self.unlink_button.setObjectName("SecondaryButton")
        self.unlink_button.setToolTip("Deja de ser un reembolso")
        layout.addWidget(self.link_button)
        layout.addWidget(self.summary_label, stretch=1)
        layout.addWidget(self.unlink_button)

        self.link_button.clicked.connect(self.choose)
        self.unlink_button.clicked.connect(lambda: self.set_expense(None))
        self.set_expense(None)

    def expense_id(self) -> int | None:
        return self._expense.id if self._expense else None

    def set_expense(self, expense: Transaction | None) -> None:
        self._expense = expense
        linked = expense is not None
        self.link_button.setVisible(not linked)
        self.summary_label.setVisible(linked)
        self.unlink_button.setVisible(linked)
        if expense is not None:
            (item,) = TransactionListBuilder(self._services).build([expense])
            remaining = self._services.transactions.refund_summary(
                expense.id, ignore_id=self._refund_id
            ).remaining
            self.summary_label.setText(
                f"{item.description} · {format_date(expense.occurred_on)} · "
                f"{expense.amount.format()} (queda {remaining.format()})"
            )
        self.changed.emit()

    def choose(self) -> None:
        picker = RefundPickerDialog(
            self._services, self._theme_manager, self.expense_id(), parent=self.window()
        )
        if picker.exec() and picker.chosen is not None:
            self.set_expense(picker.chosen)
