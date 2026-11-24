"""The tags page, its dialogs, and tags in the transactions list."""

from datetime import date

import pytest
from factories import ars, expense_draft, in_view, income_draft
from menus import run_action
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextDocumentFragment

from nodus.models.period import Month, Period
from nodus.models.transaction_filter import TransactionFilter
from nodus.ui.dialogs import confirm as confirm_dialog
from nodus.ui.dialogs.category_dialog import CategoryDialog
from nodus.ui.dialogs.tag_dialogs import MergeTagDialog, TagDialog
from nodus.ui.navigation import PageId, TransactionFocus
from nodus.ui.pages.base.summary_page import COUNT, NAME, TOTAL
from nodus.ui.pages.base.transaction_list_view import summary_html
from nodus.ui.pages.tags_page import NO_TAGS_TEXT, TagsPage
from nodus.ui.theme.theme import LIGHT
from nodus.ui.widgets.tables.transaction_table import AMOUNT, CATEGORY, SECOND_LINE_ROLE

OCTOBER_NOVEMBER = Period.of_months(Month(2026, 10), Month(2026, 11))


@pytest.fixture
def page(qtbot, services, event_bus, theme_manager) -> TagsPage:
    tags = TagsPage(services, event_bus, theme_manager)
    qtbot.addWidget(tags)
    in_view(tags, event_bus, theme_manager)
    tags.show()
    tags.period_selector.set_period(OCTOBER_NOVEMBER)  # every movement of ``populated``
    tags.refresh()
    return tags


def column(page, index: int) -> list[str]:
    return [page.proxy.index(row, index).data() for row in range(page.proxy.rowCount())]


def select(page, name: str) -> None:
    page.table.selectRow(column(page, NAME).index(name))


def actions_of(page, name: str):
    return page.row_actions(column(page, NAME).index(name))


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
    assert page.empty_state.text() == NO_TAGS_TEXT


def test_lists_most_used_first_with_totals(page, populated):
    page.refresh()

    assert column(page, NAME) == ["Viaje", "Trabajo", "Mudanza"]
    assert column(page, COUNT) == ["2", "1", "0"]
    assert column(page, TOTAL) == ["-$ 500,00", "$ 1.000,00", "—"]


def test_a_tag_used_only_in_other_periods_says_so(page, populated):
    """«Viaje» has one movement in October and one in November: in November alone it
    counts one; «Mudanza» has none anywhere and stays at 0."""
    page.period_selector.set_period(Period.of_months(Month(2026, 9)))
    page.refresh()

    counts = dict(zip(column(page, NAME), column(page, COUNT), strict=True))
    assert counts == {"Viaje": "0 · 2 en total", "Trabajo": "0 · 1 en total", "Mudanza": "0"}
    row = column(page, NAME).index("Viaje")
    assert page.proxy.index(row, COUNT).data(Qt.ItemDataRole.ToolTipRole)


def test_see_transactions_spans_the_whole_history(qtbot, services, page, populated):
    page.refresh()

    with qtbot.waitSignal(page.transactions_requested) as signal:
        run_action(actions_of(page, "Viaje"), "Ver movimientos")

    period = Period.of_months(Month(2026, 10), Month.of(date.today()))
    assert signal.args == [TransactionFocus(period, tag_id=services.tags.find("Viaje").id)]


def test_delete_several_counts_each_movement_once(
    monkeypatch, qtbot, services, event_bus, page, populated
):
    services.transactions.create(
        expense_draft(services, services.accounts.list_accounts()[0].id, ars("5"),
                      tag_names=("Viaje", "Trabajo"))
    )  # fmt: skip
    page.refresh()
    warnings = []
    monkeypatch.setattr(
        confirm_dialog, "confirm", lambda _parent, _title, text: warnings.append(text) or True
    )
    select(page, "Viaje")
    page.table.toggle_row(column(page, NAME).index("Trabajo"))

    with qtbot.waitSignal(event_bus.tags_changed):
        page.delete_button.click()

    assert warnings == [
        "Se van a eliminar 2 etiquetas. 4 movimientos pierden alguna; los movimientos no se borran."
    ]
    assert column(page, NAME) == ["Mudanza"]


def test_delete_keeps_the_movements(monkeypatch, qtbot, services, event_bus, page, populated):
    page.refresh()
    warnings = []
    monkeypatch.setattr(
        confirm_dialog, "confirm", lambda _parent, _title, text: warnings.append(text) or True
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

        assert "Unir con" in dialog.field_error(dialog.name_input)

    def test_merge_explains_and_moves_transactions(self, qtbot, services, event_bus, populated):
        viaje = services.tags.find("Viaje")
        dialog = MergeTagDialog(services, event_bus, [viaje])
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
        run_action(actions_of(tags, "Viaje"), "Ver movimientos")

        transactions = window.page(PageId.TRANSACTIONS)
        assert window.current_page is transactions
        assert transactions.tag_filter.current_id() == services.tags.find("Viaje").id
        model = transactions.model
        amounts = [model.index(row, AMOUNT).data() for row in range(model.rowCount())]
        assert amounts == ["-$ 200,00", "-$ 300,00"]
        assert model.index(0, CATEGORY).data(SECOND_LINE_ROLE) == "Viaje"
        # All spending: one figure, after what the list is.
        period = transactions.period_selector.period().label()
        assert plain(transactions.summary_label.text()) == (
            f"Viaje · {period} · 2 movimientos · -$ 500,00"
        )

        transactions.clear_filters()
        assert plain(transactions.summary_label.text()) == (
            f"{period} · 3 movimientos · Entró +$ 1.000,00 · Salió -$ 500,00 · Neto +$ 500,00"
        )


def plain(html: str) -> str:
    return QTextDocumentFragment.fromHtml(html).toPlainText()


def test_summary_without_income_or_expenses_only_counts(services):
    totals = services.dashboard.totals(TransactionFilter())

    assert plain(summary_html("", 2, totals, LIGHT)) == "2 movimientos"


def test_a_custom_color_saved_on_a_tag_is_offered_to_categories(qtbot, services, event_bus):
    dialog = TagDialog(services, event_bus)
    qtbot.addWidget(dialog)
    dialog.name_input.setText("Viaje")
    dialog.color_input.set_color("#123456")
    dialog.save_button.click()

    category = CategoryDialog(services, event_bus)
    qtbot.addWidget(category)

    assert "#123456" in category.color_input._swatches
    assert category.color_input.color() != "#123456"  # offered, not chosen


def test_a_color_is_not_remembered_when_saving_fails(qtbot, services, event_bus):
    services.tags.create("Viaje", "#95a5a6")
    dialog = TagDialog(services, event_bus)
    qtbot.addWidget(dialog)
    dialog.name_input.setText("viaje")
    dialog.color_input.set_color("#123456")

    dialog.save_button.click()

    assert services.settings.recent_colors() == []
