"""La zona horaria de un campo, en un solo sitio (BE #502, era la tercera copia)."""

from zoneinfo import ZoneInfo

import pytest

from src.modules.competition.domain.services.zona_horaria import zona_del_campo


def test_una_zona_que_existe():
    assert zona_del_campo("Atlantic/Canary") == ZoneInfo("Atlantic/Canary")


def test_sin_zona_no_hay_zona():
    assert zona_del_campo(None) is None


@pytest.mark.parametrize("rara", ["Marte/Olympus", "", "../../etc/passwd"])
def test_una_zona_que_no_existe_no_revienta(rara):
    assert zona_del_campo(rara) is None
