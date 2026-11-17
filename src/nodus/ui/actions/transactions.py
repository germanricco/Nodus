"""Editing, deleting and paying off transactions, from any list that shows them."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from PySide6.QtWidgets import QWidget

from nodus.services.container import Services
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.dialogs.transaction_dialog import TransactionDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.text.formatting import format_date
from nodus.ui.text.labels import transactions_text
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.transaction_rows import (
    TransactionListItem,
)
from nodus.ui.undo import offer_undo
from nodus.ui.widgets.tables.row_actions import Effect, RowAction


def edit_transaction(
    services: Services,
    event_bus: EventBus,
    theme_manager: ThemeManager,
    item: TransactionListItem,
    parent: QWidget,
) -> None:
    """Opens the form of ``item``, wherever its row is (Transacciones, the Dashboard)."""
    TransactionDialog(services, event_bus, theme_manager, item.transaction, parent=parent).exec()


def delete_transactions(
    services: Services, event_bus: EventBus, items: list[TransactionListItem], parent: QWidget
) -> None:
    """Deletes ``items`` after the user confirms, saying what goes with them."""
    if not items:
        return
    title = "Eliminar transacción" if len(items) == 1 else f"Eliminar {len(items)} transacciones"
    if confirm(parent, title, transaction_delete_warning(services, items)):
        services.transactions.delete_many([item.transaction.id for item in items])
        event_bus.transactions_changed.emit()


def transaction_delete_warning(services: Services, items: list[TransactionListItem]) -> str:
    if len(items) == 1:
        item = items[0]
        installment = item.transaction.installment
        if item.is_transfer:
            text = "Se va a eliminar la transferencia, con el movimiento de las dos cuentas."
        elif installment is not None:
            name = item.transaction.note or item.category_name
            text = f"Se van a eliminar las {installment.count} cuotas de «{name}»."
        else:
            text = f"Se va a eliminar «{item.description}» del {format_date(item.occurred_on)}."
    else:
        text = f"Se van a eliminar {transactions_text(len(items))}."
        if any(item.is_transfer for item in items):
            text += " Las transferencias se eliminan con el movimiento de las dos cuentas."
        if any(item.transaction.installment for item in items):
            text += " Las cuotas se eliminan con toda su compra."
    refunds = sum(
        len(services.refunds.summary(item.transaction.id).refunds)
        for item in items
        if not item.is_transfer
    )
    if refunds == 1 and len(items) == 1:
        text += " Su reembolso queda como un ingreso común."
    elif refunds == 1:
        text += " Un reembolso queda como un ingreso común."
    elif refunds:
        owner = "Sus" if len(items) == 1 else "Los"
        text += f" {owner} {refunds} reembolsos quedan como ingresos comunes."
    return text


def pay_off_actions(
    widget: QWidget, services: Services, event_bus: EventBus, item: TransactionListItem
) -> list[RowAction]:
    """For an installment: pay off the rest of its purchase, or undo it. The installments
    still to come fall on today, or on the first one if it has not come yet."""
    installment = item.transaction.installment
    if installment is None:
        return []
    installments = services.installments
    plan = installments.plan(installment.plan_id)

    def run(change: Callable[[], None], undoable: bool = False) -> None:
        change()
        event_bus.transactions_changed.emit()
        if undoable:
            offer_undo(widget, services, event_bus.transactions_changed)

    if plan.settled_on is not None:
        return [
            RowAction(
                "Deshacer adelanto",
                lambda: run(lambda: installments.unsettle(plan.id)),
                "repeat",
                effect=Effect.TOGGLE,
            )
        ]
    day = max(date.today(), plan.first_due_on)
    return [
        RowAction(
            "Adelantar las cuotas que faltan",
            lambda: run(lambda: installments.settle(plan.id, day), undoable=True),
            "skip",
            enabled=not plan.remaining(day).is_zero,
            effect=Effect.UNDOABLE,
        )
    ]
