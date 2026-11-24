"""Ctrl+K: a name leads anywhere, and what was chosen last comes first
(shell/command_palette.py)."""

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from nodus.ui.navigation import DetailId, PageId
from nodus.ui.shell.command_palette import Command, matching


def settle() -> None:
    for _ in range(3):
        QApplication.processEvents()


def command(key: str, title: str, kind: str = "Página") -> Command:
    return Command(key, title, kind, lambda: None)


class TestMatching:
    COMMANDS = [
        command("page:A", "Inicio"),
        command("page:B", "Presupuestos"),
        command("account:1", "Banco Nación", "Cuenta"),
        command("category:2", "Educación", "Categoría"),
        command("payee:3", "Café Martínez", "Beneficiario"),
    ]

    def test_finds_every_word_without_minding_accents_or_case(self):
        found = matching(self.COMMANDS, "cafe MARTI", [])
        assert [c.key for c in found] == ["payee:3"]

    def test_finds_by_kind_too(self):
        assert [c.key for c in matching(self.COMMANDS, "cuenta", [])] == ["account:1"]

    def test_names_that_start_with_it_come_first(self):
        commands = [command("x:1", "Gastos de educación"), command("x:2", "Educación")]
        assert [c.key for c in matching(commands, "educ", [])] == ["x:2", "x:1"]

    def test_empty_shows_the_recent_first_then_pages(self):
        found = matching(self.COMMANDS, "", ["category:2", "page:B"])
        assert [c.key for c in found] == ["category:2", "page:B", "page:A"]


def test_ctrl_k_opens_it_and_enter_goes_there(window, pesos, services):
    window.activateWindow()
    QTest.keyClick(window, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
    settle()
    palette = QApplication.activePopupWidget()
    assert palette is not None and palette.search_input.hasFocus()

    QTest.keyClicks(palette.search_input, "banco")
    QTest.keyClick(palette.search_input, Qt.Key.Key_Return)
    settle()

    assert window.current_page is window.detail(DetailId.ACCOUNT)
    assert services.settings.recent_commands() == [f"account:{pesos.id}"]


def test_arrows_choose_and_the_keys_are_shown(window):
    palette = window.open_palette()
    QTest.keyClicks(palette.search_input, "presu")
    assert palette.shown[0].title == "Presupuestos"
    assert palette.model.item(0, 2).text() == "Ctrl+5"

    palette.search_input.clear()
    QTest.keyClick(palette.search_input, Qt.Key.Key_Down)
    palette.run_chosen()
    settle()

    assert window.current_page_id is PageId.ACCOUNTS  # the second page
