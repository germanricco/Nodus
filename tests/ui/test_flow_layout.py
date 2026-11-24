from PySide6.QtCore import QSize
from PySide6.QtWidgets import QLabel, QLineEdit, QWidget

from nodus.ui.widgets.flow_layout import FlowLayout


def make(qtbot, texts, **options):
    host = QWidget()
    qtbot.addWidget(host)
    layout = FlowLayout(host, h_spacing=10, v_spacing=4, **options)
    labels = [QLabel(text) for text in texts]
    for label in labels:
        layout.addWidget(label)
    return host, layout, labels


def test_narrows_down_to_its_widest_item_and_wraps(qtbot):
    host, layout, labels = make(qtbot, ["uno", "un texto bastante más largo", "tres"])
    widest = max(label.sizeHint().width() for label in labels)

    assert layout.minimumSize().width() == widest
    one_line = layout.heightForWidth(10_000)
    assert layout.heightForWidth(widest) > one_line


def test_last_item_can_sit_against_the_right_edge(qtbot):
    host, layout, labels = make(qtbot, ["uno", "dos"], last_to_the_right=True)
    host.resize(400, 40)
    host.show()
    layout.activate()

    assert labels[0].geometry().left() == 0
    assert labels[1].geometry().right() == host.width() - 1


def test_a_line_narrows_its_items_before_wrapping_them(qtbot):
    host = QWidget()
    qtbot.addWidget(host)
    layout = FlowLayout(host, h_spacing=10, v_spacing=4)
    boxes = []
    for _ in range(3):
        box = QWidget()
        box.setMinimumWidth(60)
        box.sizeHint = lambda: QSize(100, 20)  # noqa: B023
        layout.addWidget(box)
        boxes.append(box)
    host.resize(3 * 80 + 2 * 10, 100)
    host.show()
    layout.activate()

    assert len({box.geometry().top() for box in boxes}) == 1  # one line
    assert all(60 <= box.width() < 100 for box in boxes)


def test_a_growing_item_takes_what_its_line_leaves(qtbot):
    host, layout, labels = make(qtbot, ["uno"])
    search = QLineEdit()
    layout.add_growing(search)
    host.resize(500, 40)
    host.show()
    layout.activate()

    assert search.geometry().right() == host.width() - 1
