from PySide6.QtWidgets import QLabel, QWidget

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
