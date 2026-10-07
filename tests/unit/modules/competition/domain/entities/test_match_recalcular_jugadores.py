"""
Recalcular los golpes de un partido sin cambiarlo (BE #502).

A las 3:00 del día de juego puede cambiar el hándicap de un jugador, y su
partido de hoy ya estaba generado. Se recalcula sobre el MISMO partido: los
móviles guardan su identificador (la cola de golpes sin conexión), así que
borrarlo y crear otro, como hace la reasignación, los dejaría colgados.
"""

import pytest

from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender


def _jugador(user_id: UserId, golpes: int) -> MatchPlayer:
    return MatchPlayer.create(
        user_id=user_id,
        playing_handicap=golpes,
        tee_color=TeeColor.YELLOW,
        tee_gender=Gender.MALE,
        strokes_received=list(range(1, golpes + 1)),
    )


A, B = UserId.generate(), UserId.generate()


def _partido() -> Match:
    return Match.create(
        round_id=RoundId.generate(),
        match_number=3,
        team_a_players=[_jugador(A, 10)],
        team_b_players=[_jugador(B, 4)],
    )


class TestRecalcular:
    def test_cambian_los_golpes_y_no_el_partido(self):
        partido = _partido()
        identificador, numero = partido.id, partido.match_number

        partido.recalcular_jugadores([_jugador(A, 6)], [_jugador(B, 4)])

        assert partido.id == identificador
        assert partido.match_number == numero
        assert partido.team_a_players[0].playing_handicap == 6
        assert partido.handicap_strokes_given == 2
        assert partido.strokes_given_to_team == "A"

    def test_si_quedan_iguales_nadie_da_golpes(self):
        partido = _partido()

        partido.recalcular_jugadores([_jugador(A, 4)], [_jugador(B, 4)])

        assert partido.handicap_strokes_given == 0
        assert partido.strokes_given_to_team == ""

    def test_puede_cambiar_quien_da_golpes(self):
        partido = _partido()

        partido.recalcular_jugadores([_jugador(A, 3)], [_jugador(B, 8)])

        assert partido.strokes_given_to_team == "B"
        assert partido.handicap_strokes_given == 5

    def test_un_partido_empezado_no_se_recalcula(self):
        partido = _partido()
        partido.start()

        with pytest.raises(ValueError, match="sin empezar"):
            partido.recalcular_jugadores([_jugador(A, 6)], [_jugador(B, 4)])

        assert partido.team_a_players[0].playing_handicap == 10

    @pytest.mark.parametrize(
        "lado_a, lado_b",
        [
            ([UserId.generate()], [B]),
            ([A], [UserId.generate()]),
            ([B], [A]),
        ],
    )
    def test_con_otros_jugadores_no_se_recalcula(self, lado_a, lado_b):
        partido = _partido()

        with pytest.raises(ValueError, match="mismos jugadores"):
            partido.recalcular_jugadores(
                [_jugador(u, 6) for u in lado_a], [_jugador(u, 4) for u in lado_b]
            )
