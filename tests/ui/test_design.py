"""The design scale's motion: every transition asks motion_ms, which honors «Reducir
animaciones»."""

from nodus.ui.theme.design import Motion, motion_ms, set_reduced_motion


def test_motion_lasts_its_step_unless_reduced():
    set_reduced_motion(False)
    assert [motion_ms(step) for step in Motion] == [int(step) for step in Motion]

    set_reduced_motion(True)
    assert [motion_ms(step) for step in Motion] == [0] * len(Motion)
