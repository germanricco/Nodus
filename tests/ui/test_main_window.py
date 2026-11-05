from nodus.ui.main_window import MainWindow


def test_main_window_opens(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    window.show()

    assert window.isVisible()
    assert window.windowTitle() == "Nodus"
