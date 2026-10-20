"""
Si se juega con hándicap o a scratch (RyderCupAM#165).

Vive en `shared` porque es del golf: lo usan la competición y la partida
rápida, que antes lo importaba del módulo de competición.
"""

import pytest

from src.shared.domain.value_objects.play_mode import PlayMode


class TestPlayMode:
    def test_son_dos_modos(self):
        assert [m.value for m in PlayMode] == ["SCRATCH", "HANDICAP"]

    @pytest.mark.parametrize(("modo", "con_handicap"), [("SCRATCH", False), ("HANDICAP", True)])
    def test_solo_el_modo_handicap_usa_handicaps(self, modo, con_handicap):
        assert PlayMode(modo).allows_handicap() is con_handicap

    def test_se_escribe_con_su_texto(self):
        assert str(PlayMode.HANDICAP) == "HANDICAP"
