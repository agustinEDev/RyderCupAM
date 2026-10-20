"""
El tipo de torneo de una competición (RyderCupAM#251).

Decidido el 1 oct 2026: modalidad → tipo. Cada tipo pertenece a una sola
modalidad, y la competición guarda solo el tipo: así no puede existir un
«stroke play + Ryder Cup». Los tipos futuros (eliminatorias, parejas, scramble)
se añaden con su implementación; hasta entonces el frontend los enseña como
«Próximamente».
"""

import pytest

from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.shared.domain.value_objects.modality import Modality


class TestTournamentType:
    def test_son_los_tipos_implementados(self):
        """Solo lo que se puede jugar: lo «próximamente» no existe aquí."""
        assert [t.value for t in TournamentType] == ["RYDER_CUP", "STABLEFORD", "MEDAL"]

    @pytest.mark.parametrize(
        ("tipo", "modalidad"),
        [
            (TournamentType.RYDER_CUP, Modality.MATCH_PLAY),
            (TournamentType.STABLEFORD, Modality.STROKE_PLAY),
            (TournamentType.MEDAL, Modality.STROKE_PLAY),
        ],
    )
    def test_cada_tipo_pertenece_a_su_modalidad(self, tipo, modalidad):
        assert tipo.modality == modalidad

    def test_ningun_tipo_se_queda_sin_modalidad(self):
        """Un tipo nuevo que no diga su modalidad rompe aquí, no en producción."""
        for tipo in TournamentType:
            assert isinstance(tipo.modality, Modality)

    @pytest.mark.parametrize(
        ("tipo", "tiene_equipos"),
        [
            (TournamentType.RYDER_CUP, True),
            (TournamentType.STABLEFORD, False),
            (TournamentType.MEDAL, False),
        ],
    )
    def test_solo_la_ryder_cup_tiene_equipos(self, tipo, tiene_equipos):
        assert tipo.has_teams is tiene_equipos

    def test_un_tipo_que_todavia_no_existe(self):
        """Una eliminatoria es «Próximamente»: no se puede crear."""
        with pytest.raises(ValueError):
            TournamentType("KNOCKOUT")

    def test_se_escribe_con_su_texto(self):
        assert str(TournamentType.STABLEFORD) == "STABLEFORD"
