"""The design scale's motion: every transition asks motion_ms, which honors «Reducir
animaciones»."""

from nodus.ui.theme.design import Motion, TextRole, design_tokens, motion_ms, set_reduced_motion


def test_motion_lasts_its_step_unless_reduced():
    set_reduced_motion(False)
    assert [motion_ms(step) for step in Motion] == [int(step) for step in Motion]

    set_reduced_motion(True)
    assert [motion_ms(step) for step in Motion] == [0] * len(Motion)


def test_roles_with_the_same_size_and_weight_stay_apart():
    """NOTE and BODY share both; each still has its own stylesheet tokens."""
    assert TextRole.NOTE is not TextRole.BODY
    assert len(TextRole) == len(TextRole.__members__)
    tokens = design_tokens()
    assert all(f"{role.name.lower()}_size" in tokens for role in TextRole.__members__.values())
