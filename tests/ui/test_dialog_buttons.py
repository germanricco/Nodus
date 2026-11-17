"""Buttons say what they do: the main button of a dialog and the one that confirms."""

import pytest
from boxes import answer_box
from factories import ars
from PySide6.QtWidgets import QMessageBox

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.ui.dialogs.account_dialog import AccountDialog
from nodus.ui.dialogs.category_dialog import CategoryDialog
from nodus.ui.dialogs.confirm import ask, confirm, delete_title, delete_with_confirm, tell
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


class TestAnswers:
    """With the real box: every way of saying no says no, and each button is there.

    A button handed to the box without being kept was once collected by Python and
    vanished, leaving the other one alone to answer Esc and the ✕ as well."""

    QUESTIONS = (
        lambda: ask(None, "Recorrido guiado", "¿Te lo muestro?", "Ver el recorrido", "Ahora no"),
        lambda: confirm(None, "Eliminar cuenta", "Se borra con sus movimientos."),
    )

    @pytest.mark.parametrize("how", ["Esc", "close", "cancel"])
    @pytest.mark.parametrize("question", QUESTIONS)
    def test_saying_no_says_no(self, qtbot, question, how):
        buttons: list[str] = []
        cancel = "Ahora no" if question is self.QUESTIONS[0] else "Cancelar"
        answer_box(cancel if how == "cancel" else how, buttons)

        assert question() is False
        assert len(buttons) == 2 and cancel in buttons

    def test_the_action_says_yes(self, qtbot):
        buttons: list[str] = []
        answer_box("Ver el recorrido", buttons)

        assert self.QUESTIONS[0]() is True


class TestDeleteWithConfirm:
    """Every delete goes through one flow: ask, delete, announce."""

    def test_cancelling_deletes_nothing_and_announces_nothing(self, qtbot, event_bus):
        deleted, announced = [], []
        event_bus.tags_changed.connect(lambda: announced.append(1))
        answer_box("Cancelar")

        result = delete_with_confirm(
            None,
            "Eliminar etiqueta",
            "Se va a eliminar.",
            lambda: deleted.append(1),
            event_bus.tags_changed,
        )

        assert (result, deleted, announced) == (False, [], [])

    def test_confirming_deletes_then_announces_each_change(self, qtbot, event_bus):
        order = []
        event_bus.tags_changed.connect(lambda: order.append("tags"))
        event_bus.transactions_changed.connect(lambda: order.append("transactions"))
        answer_box("Eliminar etiqueta")

        result = delete_with_confirm(
            None,
            "Eliminar etiqueta",
            "Se va a eliminar.",
            lambda: order.append("deleted"),
            event_bus.tags_changed,
            event_bus.transactions_changed,
        )

        assert result is True
        assert order == ["deleted", "tags", "transactions"]

    @pytest.mark.parametrize(
        ("count", "title"), [(1, "Eliminar etiqueta"), (3, "Eliminar 3 etiquetas")]
    )
    def test_the_title_counts_what_goes(self, count, title):
        assert delete_title(count, "etiqueta", "etiquetas") == title


def test_a_notice_answers_in_spanish(qtbot):
    """Nodus loads no Qt translation, so a static ``QMessageBox`` would say «OK»."""
    buttons: list[str] = []
    answer_box("Entendido", buttons)

    tell(None, "Primero, una cuenta", "Crea una en Cuentas.")

    assert buttons == ["Entendido"]
