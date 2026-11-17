"""One Nodus at a time over the same data; opening it again brings the open one forward."""

import pytest

from nodus.ui.shell.single_instance import SingleInstance, server_name


@pytest.fixture
def first(qapp, tmp_path):
    instance = SingleInstance(tmp_path)
    assert instance.acquire()
    yield instance
    instance.release()


def test_a_second_nodus_finds_the_first_and_asks_it_to_show(first, qtbot, tmp_path):
    second = SingleInstance(tmp_path)

    assert not second.acquire()
    with qtbot.waitSignal(first.show_requested, timeout=2000):
        assert second.ask_first_to_show()


def test_once_the_first_closes_another_can_open(qapp, tmp_path):
    first = SingleInstance(tmp_path)
    assert first.acquire()
    first.release()

    second = SingleInstance(tmp_path)
    assert second.acquire()
    second.release()


def test_without_a_first_one_nobody_answers(qapp, tmp_path):
    assert not SingleInstance(tmp_path).ask_first_to_show()


def test_each_data_folder_has_its_own_nodus(first, qapp, tmp_path):
    other = SingleInstance(tmp_path / "test-data")
    (tmp_path / "test-data").mkdir()

    assert other.acquire()
    other.release()
    assert server_name(tmp_path) != server_name(tmp_path / "test-data")
