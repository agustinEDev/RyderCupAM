"""
La modalidad de juego: match play o stroke play (RyderCupAM#251, #470).

Decidido el 1 oct 2026: la modalidad es el primer nivel y, dentro de ella, el
tipo de torneo. Es una pieza compartida porque la usan la competición y la
partida rápida.
"""

import pytest

from src.shared.domain.value_objects.modality import Modality


class TestModality:
    def test_son_dos_modalidades(self):
        """Cómo se gana: hoyo a hoyo contra un rival, o por el total de golpes o puntos."""
        assert [m.value for m in Modality] == ["MATCH_PLAY", "STROKE_PLAY"]

    @pytest.mark.parametrize("texto", ["MATCH_PLAY", "STROKE_PLAY"])
    def test_se_reconstruye_desde_su_texto(self, texto):
        assert Modality(texto).value == texto

    def test_una_modalidad_que_no_existe(self):
        with pytest.raises(ValueError):
            Modality("SKINS")

    def test_se_escribe_con_su_texto(self):
        assert str(Modality.STROKE_PLAY) == "STROKE_PLAY"
