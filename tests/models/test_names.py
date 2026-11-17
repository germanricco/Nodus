import pytest

from nodus.models.names import normalize_name


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Coto", "coto"),
        ("Café  Martínez", "cafe martinez"),
        ("  Verdulería «Don José»! ", "verduleria don jose"),
        ("Mercado-Libre S.A.", "mercado libre s a"),
        ("ÑANDÚ", "nandu"),
        ("¡¿!?", ""),
    ],
)
def test_normalize_name(name, expected):
    assert normalize_name(name) == expected
