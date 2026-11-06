"""The tags page, its dialogs, and tags in the transactions list."""

from datetime import date

import pytest
from factories import ars, expense_draft, income_draft
from PySide6.QtCore import Qt

from nodus.database.repositories.transaction_repository import TransactionFilter
from nodus.models.period import Month, Period
from nodus.ui.dialogs.tag_dialogs import MergeTagDialog, TagDialog
from nodus.ui.navigation import PageId, TransactionFocus
from nodus.ui.pages import tags_page
from nodus.ui.pages.summary_page import COUNT, NAME, TOTAL
from nodus.ui.pages.tags_page import NO_TAGS_TEXT, TagsPage
from nodus.ui.pages.transactions_page import totals_text
from nodus.ui.widgets.transaction_table import AMOUNT, TAGS


@pytest.fixture
def page(qtbot, services, event_bus, theme_manager) -> TagsPage:
    tags = TagsPage(services, event_bus, theme_manager)
    qtbot.addWidget(tags)
    tags.show()
    tags.refresh()
    return tags


def column(page, index: int) -> list[str]:
    return [page.proxy.index(row, index).data() for row in range(page.proxy.rowCount())]


def select(page, name: str) -> None:
    page.table.selectRow(column(page, NAME).index(name))


@pytest.fixture
def populated(services, pesos):
    """A trip with two expenses in October and November, work with one income, and a tag
    without movements."""
    for day, amount in [(date(2026, 10, 20), "300"), (date(2026, 11, 2), "200")]:
        services.transactions.create(
            expense_draft(services, pesos.id, ars(amount), day, tag_names=("Viaje",))
        )
    services.transactions.create(
        income_draft(services, pesos.id, ars("1000"), date(2026, 11, 1), tag_names=("Trabajo",))
    )
    services.tags.create("Mudanza")


def test_empty_state_explains_how_tags_appear(page):
    assert page.table.isHidden()
    assert page.empty_label.text() == NO_TAGS_TEXT


def test_lists_most_used_first_with_totals(page, populated):
    page.refresh()

    assert column(page, NAME) == ["Viaje", "Trabajo", "Mudanza"]
    assert column(page, COUNT) == ["2", "1", "0"]
    assert column(page, TOTAL) == ["-$ 500,00", "$ 1.000,00", "—"]


def test_see_transactions_spans_the_whole_history(qtbot, services, page, populated):
    page.refresh()
    select(page, "Viaje")

    with qtbot.waitSignal(page.transactions_requested) as signal:
        page.transactions_button.click()

    period = Period.of_months(Month(2026, 10), Month.of(date.today()))
    assert signal.args == [TransactionFocus(period, tag_id=services.tags.find("Viaje").id)]


def test_delete_keeps_the_movements(monkeypatch, qtbot, services, event_bus, page, populated):
    page.refresh()
    warnings = []
    monkeypatch.setattr(
        tags_page, "confirm", lambda _parent, _title, text: warnings.append(text) or True
    )
    select(page, "Viaje")

    with qtbot.waitSignal(event_bus.tags_changed):
        page.delete_button.click()

    assert warnings == [
        "Se va a eliminar «Viaje». 2 movimientos la pierden; los movimientos no se borran."
    ]
    assert column(page, NAME) == ["Trabajo", "Mudanza"]
    assert services.dashboard.totals(TransactionFilter()).expenses == ars("500")


class TestDialogs:
    def test_create_with_a_color(self, qtbot, services, event_bus, page):
        dialog = TagDialog(services, event_bus)
        qtbot.addWidget(dialog)
        dialog.name_input.setText("Mudanza")
        dialog.color_input.set_color("#ef4444")

        with qtbot.waitSignal(event_bus.tags_changed):
            qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

        assert services.tags.find("mudanza").color == "#ef4444"
        assert column(page, NAME) == ["Mudanza"]

    def test_edit_rejects_a_duplicate_name(self, qtbot, services, event_bus):
        services.tags.create("Viaje")
        work = services.tags.create("Trabajo")
        dialog = TagDialog(services, event_bus, work)
        qtbot.addWidget(dialog)
        assert dialog.color_input.color() == work.color

        dialog.name_input.setText("VIAJE")
        qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

        assert "Unir con" in dialog.error_label.text()

    def test_merge_explains_and_moves_transactions(self, qtbot, services, event_bus, populated):
        viaje = services.tags.find("Viaje")
        dialog = MergeTagDialog(services, event_bus, viaje)
        qtbot.addWidget(dialog)
        dialog.target_input.setCurrentIndex(dialog.target_input.findText("Mudanza"))

        assert dialog.result_label.text() == (
            "Sus 2 movimientos pasan a «Mudanza» y «Viaje» se elimina."
        )
        with qtbot.waitSignal(event_bus.transactions_changed):
            qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

        assert services.tags.find("Viaje") is None
        assert services.tags.transaction_count(services.tags.find("Mudanza").id) == 2


class TestTransactionsList:
    def test_tag_opens_its_movements_with_column_and_totals(self, services, window, populated):
        window.show_page(PageId.TAGS)
        tags = window.page(PageId.TAGS)
        select(tags, "Viaje")

        tags.transactions_button.click()

        transactions = window.page(PageId.TRANSACTIONS)
        assert window.current_page is transactions
        assert transactions.tag_filter.current_id() == services.tags.find("Viaje").id
        model = transactions.model
        amounts = [model.index(row, AMOUNT).data() for row in range(model.rowCount())]
        assert amounts == ["-$ 200,00", "-$ 300,00"]
        assert model.index(0, TAGS).data() == "Viaje"
        assert transactions.totals_label.text() == (
            "2 movimientos · Ingresos $ 0,00 · Gastos $ 500,00 · Neto -$ 500,00"
        )

        transactions.clear_filters()
        assert transactions.totals_label.text().startswith("3 movimientos · Ingresos $ 1.000,00")


def test_totals_text_without_income_or_expenses(services):
    totals = services.dashboard.totals(TransactionFilter())

    assert totals_text(2, totals) == "2 movimientos"
