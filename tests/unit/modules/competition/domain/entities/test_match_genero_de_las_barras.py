"""
Completar el género de la barra de los jugadores de un partido (RyderCupWeb #880).

Las Ryder SCRATCH guardaban a todos sin el género de su barra. Se rellena sin
regenerar el partido: solo a quien lo tiene vacío, y nada más cambia.
"""

from decimal import Decimal

from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender


def _jugador(tee_gender=None, color=TeeColor.YELLOW):
    return MatchPlayer.create(
        user_id=UserId.generate(),
        playing_handicap=0,
        tee_color=color,
        strokes_received=[],
        tee_gender=tee_gender,
        player_handicap=Decimal("0"),
    )


def _partido(a, b):
    return Match.create(
        round_id=RoundId.generate(), match_number=1, team_a_players=a, team_b_players=b
    )


def test_rellena_a_quien_no_tiene_genero_y_dice_cuantos():
    """
    GIVEN: Un partido con los dos jugadores sin género
    WHEN: Se completa con el género que da su barra
    THEN: Los dos lo tienen, y devuelve 2
    """
    yo, rival = _jugador(), _jugador(color=TeeColor.RED)
    partido = _partido([yo], [rival])
    generos = {yo.user_id: Gender.MALE, rival.user_id: Gender.FEMALE}

    cambiados = partido.completar_genero_de_las_barras(lambda p: generos[p.user_id])

    assert cambiados == 2
    assert [p.tee_gender for p in (*partido.team_a_players, *partido.team_b_players)] == [
        Gender.MALE,
        Gender.FEMALE,
    ]


def test_solo_cambia_el_genero():
    """
    GIVEN: Un jugador sin género
    WHEN: Se completa
    THEN: Color, golpes, hándicap y equipo siguen como estaban
    """
    yo = _jugador(color=TeeColor.WHITE)
    partido = _partido([yo], [_jugador(tee_gender=Gender.MALE)])

    partido.completar_genero_de_las_barras(lambda _: Gender.MALE)

    nuevo = partido.team_a_players[0]
    assert (nuevo.user_id, nuevo.tee_color, nuevo.playing_handicap) == (
        yo.user_id,
        TeeColor.WHITE,
        0,
    )
    assert (nuevo.strokes_received, nuevo.player_handicap) == (yo.strokes_received, Decimal("0"))


def test_quien_ya_tiene_genero_no_se_toca():
    """
    GIVEN: Un jugador que ya tiene el género de su barra
    WHEN: Se completa (aunque la regla diera otro)
    THEN: Se queda con el suyo, y no cuenta
    """
    con = _jugador(tee_gender=Gender.FEMALE)
    partido = _partido([con], [_jugador(tee_gender=Gender.MALE)])

    cambiados = partido.completar_genero_de_las_barras(lambda _: Gender.MALE)

    assert cambiados == 0
    assert partido.team_a_players[0].tee_gender == Gender.FEMALE


def test_si_la_regla_no_da_genero_se_queda_vacio():
    """
    GIVEN: Un jugador sin género cuya barra no lo tiene en el campo
    WHEN: Se completa
    THEN: Sigue sin género, y no cuenta
    """
    partido = _partido([_jugador()], [_jugador()])

    assert partido.completar_genero_de_las_barras(lambda _: None) == 0
    assert partido.team_a_players[0].tee_gender is None


def test_sin_cambios_no_se_toca_la_fecha():
    """Repetirlo sobre un partido ya completo no lo da por modificado."""
    partido = _partido([_jugador(tee_gender=Gender.MALE)], [_jugador(tee_gender=Gender.MALE)])
    antes = partido.updated_at

    partido.completar_genero_de_las_barras(lambda _: Gender.FEMALE)

    assert partido.updated_at == antes
