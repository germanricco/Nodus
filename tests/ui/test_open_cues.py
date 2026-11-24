"""One click rule for the whole app (principles 2 and 3): a row that leads to a record's
page shows it the same way everywhere (the light, the hand and a «›» at its end) and a
click on it opens that page."""

from datetime import date

from demo_data import load_demo_data
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QWidget
from qt_cleanup import flush_deleted

from nodus.ui.navigation import OPEN_TEXTS, DetailId, PageId
from nodus.ui.widgets.tables.category_line import CategoryLine
from nodus.ui.widgets.tables.row_actions import open_cue

ROWS_PER_KIND = 2  # the first rows of a list lead where the rest do


def cues(window) -> list[QLabel]:
    return [
        label
        for label in window.current_page.findChildren(QLabel, "OpenCue")
        if label.isVisibleTo(window.current_page)
    ]


def row_of(cue: QLabel) -> QWidget:
    """The row a «›» ends: the nearest widget around it with the hand."""
    widget = cue.parentWidget()
    while widget.cursor().shape() != Qt.CursorShape.PointingHandCursor:
        widget = widget.parentWidget()
    return widget


def leads_to(row: QWidget) -> DetailId:
    by_text = {detail.open_text: detail for detail in OPEN_TEXTS}
    assert row.toolTip() in by_text, f"{row.toolTip()!r} names no page"
    return by_text[row.toolTip()]


def show(qtbot, window, page_id: PageId) -> None:
    window.show_page(page_id)
    flush_deleted()  # rows replaced by a refresh are still children until deleted
    # Rows added to a shown page are shown by a queued call, after the deletions.
    QApplication.processEvents()


def test_every_row_with_a_cue_opens_the_page_it_names(qtbot, window, services):
    load_demo_data(services, date.today())
    window._event_bus.emit_all()
    opened = set()
    for page_id in PageId:
        show(qtbot, window, page_id)
        targets = [leads_to(row_of(cue)) for cue in cues(window)]
        for detail in dict.fromkeys(targets):
            for nth in range(min(targets.count(detail), ROWS_PER_KIND)):
                show(qtbot, window, page_id)  # read again: going back may rebuild the rows
                rows = [row_of(c) for c in cues(window) if leads_to(row_of(c)) is detail]
                qtbot.mouseClick(rows[nth], Qt.MouseButton.LeftButton)
                assert window.current_page is window.detail(detail), (page_id, detail, nth)
                opened.add(detail)
    # Every kind of page is reached from some list.
    assert opened == set(DetailId)


def test_a_line_without_a_page_keeps_the_room_of_its_cue(qtbot):
    without_page = CategoryLine("#000000", "Sin beneficiario", link=None)
    qtbot.addWidget(without_page)

    assert without_page.cue.isHidden()
    assert without_page.cue.sizePolicy().retainSizeWhenHidden()
    assert without_page.cursor().shape() != Qt.CursorShape.PointingHandCursor
    assert open_cue().text() == "›"
