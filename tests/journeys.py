"""Nodus used as a person uses it, for the end-to-end scenarios (``test_end_to_end.py``).

A ``Journey`` opens the window over a file of its own and does everything through the
dialogs and the pages, never through the services, so what only fails between them (a
dialog that saves what the page does not show, a change the sidebar misses) fails here.
Only what a person reads is checked through the services: the file, reopened.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from factories import category_id, light_theme, services_for
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QLabel, QWidget

from nodus.config.paths import AppPaths
from nodus.database.database import Database
from nodus.models.account import Account
from nodus.models.currency import Currency
from nodus.models.transaction import TransactionType
from nodus.services.container import Services
from nodus.ui.dialogs.account_dialog import AccountDialog
from nodus.ui.dialogs.transaction_dialog import EXPENSE_MODE, INCOME_MODE, TransactionDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import PageId
from nodus.ui.pages.base.page import Page
from nodus.ui.shell.main_window import MainWindow

NEW_GROUP = "Nuevo grupo…"


class Journey:
    """The window over ``folder``, and what a person does in it."""

    def __init__(self, qtbot, folder: Path) -> None:
        self.qtbot = qtbot
        self.paths = AppPaths(folder)
        self.paths.ensure_data_dir()
        self.database = Database.open(self.paths.database_path)
        self.services = Services.create(self.database, self.paths.backups_dir)
        self.services.settings.set_tour_offered(True)  # its offer is a test of its own
        self.event_bus = EventBus()
        self.window = MainWindow(self.services, self.event_bus, light_theme())
        qtbot.addWidget(self.window)
        self.window.show()

    # Dialogs

    def save(self, dialog) -> None:
        """Saves ``dialog`` as the user does, and checks it took what was typed."""
        self.qtbot.addWidget(dialog)
        dialog.save_button.click()
        assert not dialog.error_label.isVisibleTo(dialog), dialog.error_label.text()

    def account(
        self, name: str, balance: str, currency: Currency = Currency.ARS, group: str = ""
    ) -> Account:
        """Creates an account from Cuentas, in ``group`` (made if new) when given."""
        dialog = AccountDialog(self.services, self.event_bus, parent=self.window)
        dialog.name_input.setText(name)
        dialog.currency_input.setCurrentIndex(dialog.currency_input.findData(currency))
        dialog.balance_input.line_edit.setText(balance)
        if group:
            picker = dialog.group_picker
            index = picker.input.findText(group)
            picker.input.setCurrentIndex(index if index >= 0 else picker.input.findText(NEW_GROUP))
            if index < 0:
                picker.name_input.setText(group)
        self.save(dialog)
        return next(a for a in self.services.accounts.list_accounts() if a.name == name)

    def transaction_dialog(self, mode: int, account: Account, amount: str) -> TransactionDialog:
        """«Agregar transacción», with the kind, account and amount typed in."""
        dialog = TransactionDialog(
            self.services, self.event_bus, self.window.theme_manager, parent=self.window
        )
        self.qtbot.addWidget(dialog)
        dialog.mode_input.set_index(mode)
        dialog.account_input.select(account.id)
        dialog.amount_input.line_edit.setText(amount)
        return dialog

    def spend(self, account: Account, amount: str, category: str, note: str = "") -> None:
        dialog = self.transaction_dialog(EXPENSE_MODE, account, amount)
        self.pick_category(dialog, category, TransactionType.EXPENSE)
        dialog.note_input.setText(note)
        self.save(dialog)

    def earn(self, account: Account, amount: str, category: str) -> None:
        dialog = self.transaction_dialog(INCOME_MODE, account, amount)
        self.pick_category(dialog, category, TransactionType.INCOME)
        self.save(dialog)

    def pick_category(self, dialog, name: str, kind: TransactionType) -> None:
        """Chooses ``name`` from the list, as the user does: the form reacts to it."""
        dialog.category_input.select(category_id(self.services, name, kind))
        dialog.category_input.activated.emit(dialog.category_input.currentIndex())

    # Pages

    def show(self, page_id: PageId) -> Page:
        self.window.show_page(page_id)
        return self.window.page(page_id)

    def texts(self, widget: QWidget) -> list[str]:
        """The labels of ``widget``, once the rows a refresh replaced are gone."""
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        return [label.text() for label in widget.findChildren(QLabel)]

    def column(self, page: Page, index: int) -> list[str]:
        """The texts of a column of the movements list of ``page``."""
        model = page.model
        return [model.data(model.index(row, index)) for row in range(model.rowCount())]

    def toasts(self) -> list[str]:
        return [toast.text for toast in self.window.toasts.toasts]

    # The file

    @contextmanager
    def reopened(self) -> Iterator[Services]:
        """Closes Nodus and opens the file again: what was saved is what comes back."""
        self.window.close()
        self.database.close()
        database = Database.open(self.paths.database_path)
        try:
            yield services_for(database)
        finally:
            database.close()
