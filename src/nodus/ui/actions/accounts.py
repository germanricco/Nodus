"""Editing, archiving and deleting an account, from its row in Cuentas or its own page."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from nodus.models.account import Account
from nodus.services.container import Services
from nodus.ui.dialogs.account_dialog import AccountDialog
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.event_bus import EventBus


def account_delete_warning(services: Services, account: Account) -> str:
    """What deleting ``account`` takes with it: its movements, transfers and charges."""
    movements, transfers = services.accounts.transaction_count(account.id)
    sentences = [f"Se va a eliminar la cuenta «{account.name}»."]
    if movements == 0:
        sentences.append("No tiene transacciones.")
    elif movements == 1:
        sentences.append("Su única transacción también se elimina.")
    else:
        sentences.append(f"Sus {movements} transacciones también se eliminan.")
    if transfers == 1:
        sentences.append("Incluye una transferencia, así que cambia el saldo de la otra cuenta.")
    elif transfers > 1:
        sentences.append(
            f"Incluye {transfers} transferencias, así que cambia el saldo de las otras cuentas."
        )
    charges = services.recurring.count_for_account(account.id)
    if charges == 1:
        sentences.append("También se elimina su cargo recurrente.")
    elif charges > 1:
        sentences.append(f"También se eliminan sus {charges} cargos recurrentes.")
    if movements:
        sentences.append("Para conservar el historial, archívala en su lugar.")
    return " ".join(sentences)


def delete_account(
    parent: QWidget, services: Services, event_bus: EventBus, account: Account
) -> bool:
    """Deletes ``account`` once the user confirms, saying what goes with it."""
    if not confirm(parent, "Eliminar cuenta", account_delete_warning(services, account)):
        return False
    services.accounts.delete(account.id)
    event_bus.accounts_changed.emit()
    event_bus.transactions_changed.emit()
    return True


def edit_account(
    parent: QWidget, services: Services, event_bus: EventBus, account: Account | None = None
) -> None:
    """Opens the account form: a new account, or ``account`` to edit."""
    AccountDialog(services, event_bus, account, parent=parent.window()).exec()


def toggle_account_archived(services: Services, event_bus: EventBus, account: Account) -> None:
    """Archives ``account``, or brings it back if it was archived."""
    services.accounts.set_archived(account.id, not account.is_archived)
    event_bus.accounts_changed.emit()
