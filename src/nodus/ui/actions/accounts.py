"""Editing, archiving and deleting an account, from its row in Cuentas or its own page."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from nodus.i18n import _, ngettext
from nodus.models.account import Account
from nodus.services.container import Services
from nodus.ui.dialogs.account_dialog import AccountDialog
from nodus.ui.dialogs.confirm import delete_with_confirm
from nodus.ui.event_bus import EventBus


def account_delete_warning(services: Services, account: Account) -> str:
    """What deleting ``account`` takes with it: its movements, transfers and charges."""
    movements, transfers = services.accounts.transaction_count(account.id)
    sentences = [_("Se va a eliminar la cuenta «{name}».").format(name=account.name)]
    if movements == 0:
        sentences.append(_("No tiene transacciones."))
    else:
        sentences.append(
            ngettext(
                "Su única transacción también se elimina.",
                "Sus {count} transacciones también se eliminan.",
                movements,
            ).format(count=movements)
        )
    if transfers:
        sentences.append(
            ngettext(
                "Incluye una transferencia, así que cambia el saldo de la otra cuenta.",
                "Incluye {count} transferencias, así que cambia el saldo de las otras cuentas.",
                transfers,
            ).format(count=transfers)
        )
    charges = services.recurring.count_for_account(account.id)
    if charges:
        sentences.append(
            ngettext(
                "También se elimina su cargo recurrente.",
                "También se eliminan sus {count} cargos recurrentes.",
                charges,
            ).format(count=charges)
        )
    if movements:
        sentences.append(_("Para conservar el historial, archívala en su lugar."))
    return " ".join(sentences)


def delete_account(
    parent: QWidget, services: Services, event_bus: EventBus, account: Account
) -> bool:
    """Deletes ``account`` once the user confirms, saying what goes with it."""
    return delete_with_confirm(
        parent,
        _("Eliminar cuenta"),
        account_delete_warning(services, account),
        lambda: services.accounts.delete(account.id),
        event_bus.accounts_changed,
        event_bus.transactions_changed,
    )


def edit_account(
    parent: QWidget, services: Services, event_bus: EventBus, account: Account | None = None
) -> None:
    """Opens the account form: a new account, or ``account`` to edit."""
    AccountDialog(services, event_bus, account, parent=parent.window()).exec()


def toggle_account_archived(services: Services, event_bus: EventBus, account: Account) -> None:
    """Archives ``account``, or brings it back if it was archived."""
    services.accounts.set_archived(account.id, not account.is_archived)
    event_bus.accounts_changed.emit()
