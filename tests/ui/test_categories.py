from datetime import date

import pytest
from factories import ars, category_id, expense_draft, in_view, light_theme
from menus import run_action, texts
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel

from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
from nodus.services.reports.category_report_service import CategoryFigures
from nodus.ui.dialogs import confirm as confirm_dialog
from nodus.ui.dialogs.category_dialog import (
    NO_PARENT_LABEL,
    CategoryDialog,
    MergeCategoryDialog,
)
from nodus.ui.pages import categories_page
from nodus.ui.pages.categories_page import CategoriesPage, CategoryRow
from nodus.ui.widgets.empty_state import EmptyState

EXPENSE = TransactionType.EXPENSE
INCOME = TransactionType.INCOME
NOVEMBER = Period.of_months(Month(2026, 11))


@pytest.fixture
def page(qtbot, services, event_bus) -> CategoriesPage:
    categories = CategoriesPage(services, event_bus, light_theme())
    qtbot.addWidget(categories)
    in_view(categories, event_bus)
    categories.refresh()
    return categories


def rows(page) -> list[CategoryRow]:
    return [row for row in page.findChildren(CategoryRow) if row.isVisibleTo(page)]


def row_named(page, name: str, kind: TransactionType = EXPENSE) -> CategoryRow:
    return next(r for r in rows(page) if r.category.name == name and r.category.kind is kind)


def action(row: CategoryRow, text: str):
    return next(a for a in row.actions() if a.text == text)


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

    def test_parent_choices_follow_kind_and_exclude_system_ones(self, qtbot, services, event_bus):
        """«Otros» and «Reembolsos» cannot hold subcategories."""
        dialog = make_dialog(qtbot, services, event_bus, kind=INCOME)

        choices = [dialog.parent_input.itemText(i) for i in range(dialog.parent_input.count())]

        assert choices == [NO_PARENT_LABEL, "Sueldo", "Trabajo freelance"]

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

    def test_otros_only_opens_and_subcategories_cannot_nest(self, services, page):
        vivienda = category_id(services, "Vivienda", EXPENSE)
        services.categories.create("Alquiler", EXPENSE, "#000000", parent_id=vivienda)
        page.refresh()

        otros = row_named(page, "Otros")
        assert texts(otros.actions()) == ["Abrir", "Ver movimientos"]
        tags = [label for label in otros.findChildren(QLabel) if label.objectName() == "Tag"]
        assert [tag.text() for tag in tags] == ["sistema"]
        assert tags[0].toolTip() == categories_page.SYSTEM_HINT
        assert texts(row_named(page, "Alquiler").actions()) == [
            "Abrir",
            "Ver movimientos",
            "Editar",
            "Unir con…",
            "Eliminar",
        ]
        assert "Agregar subcategoría" in texts(row_named(page, "Vivienda").actions())

    def test_see_movements_spans_the_category_history(self, qtbot, services, page, pesos):
        ocio = category_id(services, "Ocio", EXPENSE)
        services.transactions.create(
            expense_draft(services, pesos.id, ars("10"), date(2026, 3, 5), category_id=ocio)
        )
        page.refresh()
        assert not action(row_named(page, "Ropa"), "Ver movimientos").enabled  # no movements

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
            confirm_dialog, "confirm", lambda _parent, _title, text: warnings.append(text) or True
        )

        with qtbot.waitSignal(event_bus.transactions_changed):
            run_action(row_named(page, "Ocio").actions(), "Eliminar")

        assert warnings == ["Se va a eliminar «Ocio». Su única transacción pasa a «Otros»."]
        assert "Ocio" not in [r.category.name for r in rows(page)]

    def test_delete_is_cancelled_when_not_confirmed(self, qtbot, monkeypatch, services, page):
        monkeypatch.setattr(confirm_dialog, "confirm", lambda *_args: False)

        run_action(row_named(page, "Ocio").actions(), "Eliminar")

        assert "Ocio" in [c.name for c in services.categories.list_categories(EXPENSE)]


class TestFoldingSubcategories:
    """A category and its subcategories are one group, which folds under its «▾»."""

    @pytest.fixture
    def housing(self, services) -> int:
        vivienda = category_id(services, "Vivienda", EXPENSE)
        for name in ("Alquiler", "Expensas"):
            services.categories.create(name, EXPENSE, "#000000", parent_id=vivienda)
        return vivienda

    def test_only_a_category_with_subcategories_folds(self, services, page, housing):
        page.refresh()

        assert row_named(page, "Vivienda").fold_button.isVisibleTo(page)
        for name in ("Alquiler", "Ocio", "Otros"):
            fold = row_named(page, name).fold_button
            assert fold.isHidden() and fold.sizePolicy().retainSizeWhenHidden()

    def test_folding_hides_its_subcategories_and_says_how_many(
        self, qtbot, services, page, housing
    ):
        page.refresh()
        vivienda = row_named(page, "Vivienda")
        assert not vivienda.fold_button.folded
        assert vivienda.subcategories_label.isHidden()

        qtbot.mouseClick(vivienda.fold_button, Qt.MouseButton.LeftButton)

        names = [r.category.name for r in rows(page)]
        assert "Vivienda" in names and "Alquiler" not in names and "Expensas" not in names
        assert vivienda.fold_button.folded
        assert vivienda.subcategories_label.isVisibleTo(page)
        assert vivienda.subcategories_label.text() == "2 subcategorías"
        assert services.settings.folded_categories() == {housing}

        qtbot.mouseClick(vivienda.fold_button, Qt.MouseButton.LeftButton)
        assert "Alquiler" in [r.category.name for r in rows(page)]
        assert services.settings.folded_categories() == set()

    def test_folded_stays_folded_and_still_adds_them_up(self, services, pesos, page, housing):
        services.transactions.create(
            expense_draft(
                services, pesos.id, ars("400"), date.today(),
                category_id=category_id(services, "Alquiler", EXPENSE),
            )
        )  # fmt: skip
        services.settings.set_folded_categories({housing})

        page.refresh()

        vivienda = row_named(page, "Vivienda")
        assert vivienda.fold_button.folded
        assert "Alquiler" not in [r.category.name for r in rows(page)]
        assert vivienda.amount_label.text() == "$ 400,00"

    def test_a_search_shows_what_it_found_in_a_folded_category(self, services, page, housing):
        services.settings.set_folded_categories({housing})
        page.refresh()

        page.search_input.setText("alqui")

        assert [r.category.name for r in rows(page)] == ["Vivienda", "Alquiler"]
        page.search_input.clear()
        assert "Alquiler" not in [r.category.name for r in rows(page)]

    def test_a_chosen_subcategory_stays_chosen_while_folded(self, qtbot, services, page, housing):
        page.refresh()
        row_named(page, "Alquiler").check_box.setChecked(True)
        row_named(page, "Ocio").check_box.setChecked(True)

        qtbot.mouseClick(row_named(page, "Vivienda").fold_button, Qt.MouseButton.LeftButton)

        assert {c.name for c in page.chosen} == {"Alquiler", "Ocio"}
        assert page.selection_bar.isVisibleTo(page)

    def test_a_line_between_groups_never_inside_one(self, services, page, housing):
        page.refresh()
        vivienda = row_named(page, "Vivienda")
        group = vivienda.parentWidget()

        assert [r.category.name for r in group.findChildren(CategoryRow)] == [
            "Vivienda", "Alquiler", "Expensas",
        ]  # fmt: skip
        assert not group.findChildren(QFrame, "Separator")
        card_body = group.parentWidget()
        assert card_body.findChildren(QFrame, "Separator")


class TestSeveralChosen:
    """Two or more chosen categories are merged or deleted together."""

    def choose(self, page, *names):
        for name in names:
            row_named(page, name).check_box.setChecked(True)

    def test_two_chosen_turn_the_header_into_the_selection_bar(self, page):
        self.choose(page, "Ocio")
        assert not page.selection_bar.isVisibleTo(page)

        self.choose(page, "Ropa")

        assert page.selection_bar.isVisibleTo(page)
        assert page.selection_bar.count_label.text() == "2 seleccionadas"
        assert page.merge_button.isEnabled()

    def test_esc_lets_them_go(self, qtbot, page):
        self.choose(page, "Ocio", "Ropa")

        qtbot.keyClick(page, Qt.Key.Key_Escape)

        assert page.chosen == []
        assert not row_named(page, "Ocio").check_box.isChecked()
        assert not page.selection_bar.isVisibleTo(page)

    def test_system_categories_cannot_be_chosen(self, page):
        otros = next(r for r in rows(page) if r.category.is_system)
        assert not otros.check_box.isVisibleTo(page)

    def test_two_kinds_cannot_merge(self, page):
        self.choose(page, "Ocio")
        row_named(page, "Sueldo", INCOME).check_box.setChecked(True)

        assert not page.merge_button.isEnabled()

    def test_deleting_them_together_after_one_confirmation(
        self, qtbot, monkeypatch, services, event_bus, page, pesos
    ):
        ocio = category_id(services, "Ocio", EXPENSE)
        services.transactions.create(expense_draft(services, pesos.id, ars("10"), category_id=ocio))
        page.refresh()
        warnings = []
        monkeypatch.setattr(
            confirm_dialog, "confirm", lambda _parent, _title, text: warnings.append(text) or True
        )
        self.choose(page, "Ocio", "Ropa")

        with qtbot.waitSignal(event_bus.categories_changed):
            qtbot.keyClick(page, Qt.Key.Key_Delete)

        assert warnings == [
            (
                "Se van a eliminar 2 categorías. "
                "Entre todas tienen una transacción, que pasa a «Otros»."
            )
        ]
        assert not {"Ocio", "Ropa"} & {r.category.name for r in rows(page)}
        assert page.chosen == []
        assert not page.selection_bar.isVisibleTo(page)

    def test_the_choice_survives_a_refresh_but_not_a_deletion(self, services, page):
        self.choose(page, "Ocio", "Ropa")
        services.categories.delete(category_id(services, "Ropa", EXPENSE))

        page.refresh()

        assert [c.name for c in page.chosen] == ["Ocio"]
        assert row_named(page, "Ocio").check_box.isChecked()
        assert not page.selection_bar.isVisibleTo(page)

    def test_merging_them_keeps_the_one_chosen(self, qtbot, services, event_bus, pesos):
        ocio, ropa = category_id(services, "Ocio", EXPENSE), category_id(services, "Ropa", EXPENSE)
        services.transactions.create(expense_draft(services, pesos.id, ars("10"), category_id=ocio))
        dialog = MergeCategoryDialog(
            services, event_bus, [services.categories.get(i) for i in (ocio, ropa)]
        )
        qtbot.addWidget(dialog)
        dialog.target_input.setCurrentIndex(dialog.target_input.findText("Ropa"))

        assert dialog.windowTitle() == "Unir 2 categorías"
        with qtbot.waitSignal(event_bus.categories_changed):
            qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

        names = [c.name for c in services.categories.list_categories(EXPENSE)]
        assert "Ropa" in names and "Ocio" not in names
        assert services.categories.transaction_count(ropa) == 1


class TestCategoryFigures:
    """What the list says of each category in the period."""

    @pytest.fixture
    def november(self, services, page, pesos):
        """Two expenses in November 2026 and one in October, out of the period."""
        for amount, name, day in (
            ("300", "Ocio", date(2026, 11, 3)),
            ("100", "Supermercado y comida", date(2026, 11, 4)),
            ("999", "Ropa", date(2026, 10, 30)),
        ):
            services.transactions.create(
                expense_draft(services, pesos.id, ars(amount), day,
                              category_id=category_id(services, name, EXPENSE))
            )  # fmt: skip
        page.period_selector.set_period(NOVEMBER)
        page.refresh()

    def test_amounts_and_shares_from_the_largest_down(self, page, november):
        expense_names = [r.category.name for r in rows(page) if r.category.kind is EXPENSE]
        assert expense_names[:2] == ["Ocio", "Supermercado y comida"]
        ocio = row_named(page, "Ocio")
        assert ocio.amount_label.text() == "$ 300,00"
        assert ocio.percent_label.text() == "75 %"
        assert ocio.bar.fraction == pytest.approx(0.75)
        assert row_named(page, "Ropa").amount_label.text() == "Sin gastos"
        assert not row_named(page, "Ropa").bar.isVisibleTo(page)
        assert row_named(page, "Sueldo", INCOME).amount_label.text() == "Sin ingresos"

    def test_another_period_changes_the_figures(self, page, november):
        page.period_selector.set_period(Period.of_months(Month(2026, 10)))

        assert rows(page)[0].category.name == "Ropa"
        assert rows(page)[0].amount_label.text() == "$ 999,00"

    def test_hidden_amounts_show_only_the_currency(self, services, event_bus, page, november):
        services.settings.set_amounts_hidden(True)
        event_bus.amounts_hidden_changed.emit(True)

        assert row_named(page, "Ocio").amount_label.text() == "$ ••••"

    def test_budgets_stay_in_presupuestos(self, services, page, november):
        ocio = category_id(services, "Ocio", EXPENSE)
        services.budgets.set_limit(ocio, Month(2026, 11), ars("1000"))
        page.refresh()

        assert row_named(page, "Ocio").findChildren(QLabel, "ChangeBadge") == []

    def test_the_search_ignores_accents_and_keeps_the_parent(self, services, page):
        vivienda = category_id(services, "Vivienda", EXPENSE)
        services.categories.create("Alquiler", EXPENSE, "#000000", parent_id=vivienda)
        page.refresh()

        page.search_input.setText("ALQUILER")
        assert [r.category.name for r in rows(page)] == ["Vivienda", "Alquiler"]

        page.search_input.setText("educacion")
        assert [r.category.name for r in rows(page)] == ["Educación"]

        page.search_input.setText("zzz")
        assert rows(page) == []
        empty = page.findChild(EmptyState)
        assert empty.isVisibleTo(page)

    def test_more_refunds_than_spending_show_no_bar(self, qtbot, services):
        ropa = services.categories.get(category_id(services, "Ropa", EXPENSE))
        row = CategoryRow(CategoryFigures(ropa, ars("-45"), 2, -0.06), light_theme().theme)
        qtbot.addWidget(row)

        assert row.amount_label.text() == "-$ 45,00"
        assert row.bar.isHidden()
        assert row.percent_label.text() == ""
