"""
Rehacer los jugadores de un partido sin empezar (BE #912): al cambiar unas barras,
lo que queda por jugar sale con las nuevas; lo empezado no se toca.
"""

import pytest

from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender


def _jugador(user_id, golpes=0, color=TeeColor.YELLOW):
    return MatchPlayer.create(
        user_id=user_id,
        playing_handicap=golpes,
        tee_color=color,
        tee_gender=Gender.MALE,
        strokes_received=list(range(1, golpes + 1)),
    )


@pytest.fixture
def ana():
    return UserId.generate()


@pytest.fixture
def bea():
    return UserId.generate()


def _partido(ana, bea):
    return Match.create(
        round_id=RoundId.generate(),
        match_number=1,
        team_a_players=[_jugador(ana, 2)],
        team_b_players=[_jugador(bea, 5)],
    )


def test_recalcular_jugadores_sin_empezar_pone_los_nuevos_y_su_ventaja(ana, bea):
    """
    Given un partido programado en el que B recibe 3 golpes
    When se rehacen sus jugadores con A en rojas recibiendo 7
    Then el partido lleva los nuevos y la ventaja pasa a A (2 golpes)
    """
    partido = _partido(ana, bea)
    assert (partido.handicap_strokes_given, partido.strokes_given_to_team) == (3, "B")

    partido.recalcular_jugadores([_jugador(ana, 7, TeeColor.RED)], [_jugador(bea, 5)])

    assert partido.find_player(ana).tee_color == TeeColor.RED
    assert (partido.handicap_strokes_given, partido.strokes_given_to_team) == (2, "A")
    assert partido.status == MatchStatus.SCHEDULED


def test_recalcular_jugadores_de_un_partido_empezado_no_se_puede(ana, bea):
    """
    Given un partido ya empezado
    When se intentan rehacer sus jugadores
    Then no se puede: lo empezado no se toca
    """
    partido = _partido(ana, bea)
    partido.start()

    with pytest.raises(ValueError):
        partido.recalcular_jugadores([_jugador(ana, 7)], [_jugador(bea, 5)])

    assert partido.find_player(ana).playing_handicap == 2


def test_recalcular_jugadores_no_cambia_quien_juega(ana, bea):
    """
    Given un partido programado
    When se intenta rehacer con otro jugador
    Then no se puede: eso es reasignar, no recalcular
    """
    partido = _partido(ana, bea)

    with pytest.raises(ValueError):
        partido.recalcular_jugadores([_jugador(UserId.generate(), 7)], [_jugador(bea, 5)])
