from datetime import date

import pytest
from factories import ars, category_id, expense_draft
from menus import run_action, texts
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from nodus.models.transaction import TransactionType
from nodus.ui.dialogs.category_dialog import NO_PARENT_LABEL, CategoryDialog
from nodus.ui.pages import categories_page
from nodus.ui.pages.categories_page import CategoriesPage, CategoryRow

EXPENSE = TransactionType.EXPENSE
INCOME = TransactionType.INCOME


@pytest.fixture
def page(qtbot, services, event_bus) -> CategoriesPage:
    categories = CategoriesPage(services, event_bus)
    qtbot.addWidget(categories)
    categories.refresh()
    return categories


def rows(page) -> list[CategoryRow]:
    return [row for row in page.findChildren(CategoryRow) if row.isVisibleTo(page)]


def row_named(page, name: str, kind: TransactionType = EXPENSE) -> CategoryRow:
    return next(r for r in rows(page) if r.category.name == name and r.category.kind is kind)


def make_dialog(qtbot, services, event_bus, **kwargs) -> CategoryDialog:
    dialog = CategoryDialog(services, event_bus, **kwargs)
    qtbot.addWidget(dialog)
    return dialog


class TestCategoryDialog:
    def test_creates_income_category_with_color(self, qtbot, services, event_bus):
        dialog = make_dialog(qtbot, services, event_bus, kind=INCOME)
        dialog.name_input.setText("Alquileres cobrados")
        dialog.color_input.set_color("#8e44ad")

        with qtbot.waitSignal(event_bus.categories_changed):
            qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

        created = next(
            c for c in services.categories.list_categories(INCOME)
            if c.name == "Alquileres cobrados"
        )  # fmt: skip
        assert created.color == "#8e44ad"
        assert created.parent_id is None

    def test_parent_choices_follow_kind_and_exclude_otros(self, qtbot, services, event_bus):
        dialog = make_dialog(qtbot, services, event_bus, kind=INCOME)

        choices = [dialog.parent_input.itemText(i) for i in range(dialog.parent_input.count())]

        assert choices == [NO_PARENT_LABEL, "Reembolsos", "Sueldo", "Trabajo freelance"]

    def test_creates_subcategory_with_preselected_parent(self, qtbot, services, event_bus):
        vivienda = category_id(services, "Vivienda", EXPENSE)
        dialog = make_dialog(qtbot, services, event_bus, kind=EXPENSE, parent_id=vivienda)
        dialog.name_input.setText("Expensas")

        qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

        node = next(
            n for n in services.categories.category_tree(EXPENSE) if n.category.id == vivienda
        )
        assert [child.name for child in node.children] == ["Expensas"]

    def test_edit_locks_kind_and_parent(self, qtbot, services, event_bus):
        ocio = services.categories.get(category_id(services, "Ocio", EXPENSE))
        dialog = make_dialog(qtbot, services, event_bus, category=ocio)

        assert dialog.name_input.text() == "Ocio"
        assert not dialog.kind_input.isEnabled()
        assert not dialog.parent_input.isEnabled()

        dialog.name_input.setText("Salidas")
        qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

        assert services.categories.get(ocio.id).name == "Salidas"
        assert services.categories.get(ocio.id).color == ocio.color

    def test_duplicate_name_shows_error(self, qtbot, services, event_bus):
        dialog = make_dialog(qtbot, services, event_bus)
        dialog.name_input.setText("Salud")

        qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

        assert dialog.field_error(dialog.name_input) == "Ya existe una categoría con ese nombre."


class TestCategoriesPage:
    def test_lists_both_kinds_with_subcategories_after_parent(self, services, page):
        vivienda = category_id(services, "Vivienda", EXPENSE)
        services.categories.create("Alquiler", EXPENSE, "#000000", parent_id=vivienda)

        page.refresh()

        expense_names = [r.category.name for r in rows(page) if r.category.kind is EXPENSE]
        assert expense_names[-3:] == ["Vivienda", "Alquiler", "Otros"]
        income_names = [r.category.name for r in rows(page) if r.category.kind is INCOME]
        assert income_names == ["Reembolsos", "Sueldo", "Trabajo freelance", "Otros"]

    def test_otros_only_shows_movements_and_subcategories_cannot_nest(self, services, page):
        vivienda = category_id(services, "Vivienda", EXPENSE)
        services.categories.create("Alquiler", EXPENSE, "#000000", parent_id=vivienda)
        page.refresh()

        otros = row_named(page, "Otros")
        assert texts(otros.actions()) == ["Ver movimientos"]
        tags = [label for label in otros.findChildren(QLabel) if label.objectName() == "Tag"]
        assert [tag.text() for tag in tags] == ["sistema"]
        assert tags[0].toolTip() == categories_page.SYSTEM_HINT
        assert texts(row_named(page, "Alquiler").actions()) == [
            "Ver movimientos",
            "Editar",
            "Eliminar",
        ]
        assert "Agregar subcategoría" in texts(row_named(page, "Vivienda").actions())

    def test_see_movements_spans_the_category_history(self, qtbot, services, page, pesos):
        ocio = category_id(services, "Ocio", EXPENSE)
        services.transactions.create(
            expense_draft(services, pesos.id, ars("10"), date(2026, 3, 5), category_id=ocio)
        )
        page.refresh()
        assert not row_named(page, "Ropa").actions()[0].enabled  # no movements

        with qtbot.waitSignal(page.transactions_requested) as signal:
            run_action(row_named(page, "Ocio").actions(), "Ver movimientos")

        focus = signal.args[0]
        assert (focus.category_id, focus.period.start) == (ocio, date(2026, 3, 1))

    def test_delete_after_confirmation_moves_transactions(
        self, qtbot, monkeypatch, services, event_bus, page, pesos
    ):
        ocio = category_id(services, "Ocio", EXPENSE)
        services.transactions.create(expense_draft(services, pesos.id, ars("10"), category_id=ocio))
        warnings = []
        monkeypatch.setattr(
            categories_page, "confirm", lambda _parent, _title, text: warnings.append(text) or True
        )

        with qtbot.waitSignal(event_bus.transactions_changed):
            run_action(row_named(page, "Ocio").actions(), "Eliminar")

        assert warnings == ["Se va a eliminar «Ocio». Su única transacción pasa a «Otros»."]
        assert "Ocio" not in [r.category.name for r in rows(page)]

    def test_delete_is_cancelled_when_not_confirmed(self, qtbot, monkeypatch, services, page):
        monkeypatch.setattr(categories_page, "confirm", lambda *_args: False)

        run_action(row_named(page, "Ocio").actions(), "Eliminar")

        assert "Ocio" in [c.name for c in services.categories.list_categories(EXPENSE)]
