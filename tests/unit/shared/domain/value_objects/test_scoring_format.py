"""
Cómo se puntúa un stroke play: Medal (golpes) o Stableford (puntos) (RyderCupAM#165).

Vive en `shared` porque lo usarán la partida rápida y la competición stroke
play (#251). Sabe su porcentaje WHS por defecto, igual que `MatchFormat` sabe
el suyo: antes era la constante FREE_PLAY_ALLOWANCE de la partida rápida.
"""

import pytest

from src.shared.domain.value_objects.scoring_format import ScoringFormat


class TestScoringFormat:
    def test_son_medal_y_stableford(self):
        assert [f.value for f in ScoringFormat] == ["MEDAL", "STABLEFORD"]

    def test_se_escribe_con_su_texto(self):
        assert str(ScoringFormat.STABLEFORD) == "STABLEFORD"


class TestDefaultAllowance:
    @pytest.mark.parametrize("formato", list(ScoringFormat))
    def test_stroke_play_individual_al_95(self, formato):
        """El estándar WHS de stroke play individual, para Medal y para Stableford."""
        assert formato.default_allowance == 95
