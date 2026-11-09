"""Buttons say what they do: the main button of a dialog and the one that confirms."""

from factories import ars
from PySide6.QtWidgets import QMessageBox

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.ui.dialogs.account_dialog import AccountDialog
from nodus.ui.dialogs.category_dialog import CategoryDialog
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.dialogs.form_dialog import SAVE_CHANGES


class TestConfirm:
    def run(self, monkeypatch, *args, **kwargs) -> dict:
        """Calls ``confirm`` without showing the box, recording its buttons."""
        seen: dict = {}

        def fake_exec(box: QMessageBox) -> int:
            seen["texts"] = [button.text() for button in box.buttons()]
            seen["red"] = [b.text() for b in box.buttons() if b.objectName() == "DangerButton"]
            seen["default"] = box.defaultButton().text()
            return 0

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        seen["result"] = confirm(None, *args, **kwargs)
        return seen

    def test_the_button_is_the_title_in_red(self, qtbot, monkeypatch):
        seen = self.run(monkeypatch, "Eliminar 3 transacciones", "Se van a eliminar.")

        assert seen["red"] == ["Eliminar 3 transacciones"]
        assert seen["default"] == "Cancelar"
        assert seen["result"] is False

    def test_a_given_action_names_the_button(self, qtbot, monkeypatch):
        seen = self.run(monkeypatch, "Restaurar copia", "Reemplaza tus datos.", action="Restaurar")

        assert seen["red"] == ["Restaurar"]


class TestMainButton:
    def test_creating_says_what_it_adds(self, qtbot, services, event_bus):
        dialog = AccountDialog(services, event_bus)
        qtbot.addWidget(dialog)

        assert dialog.save_button.text() == "Agregar cuenta"

    def test_editing_saves_changes(self, qtbot, services, event_bus):
        account = services.accounts.create("Caja", AccountType.CASH, Currency.ARS, ars("0"))
        dialog = AccountDialog(services, event_bus, account)
        qtbot.addWidget(dialog)

        assert dialog.save_button.text() == SAVE_CHANGES

    def test_a_subcategory_says_so(self, qtbot, services, event_bus):
        parent_id = services.categories.list_categories()[0].id
        dialog = CategoryDialog(services, event_bus, parent_id=parent_id)
        qtbot.addWidget(dialog)

        assert dialog.save_button.text() == "Agregar subcategoría"
