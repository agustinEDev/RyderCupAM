"""
La tarjeta de un jugador de stroke play con sus hoyos validados (#251, PR 5).

Solo cuentan los validados (jugador y marcador coinciden). Golpes recibidos y
par de cada hoyo salen de la foto de su partida (P12).

| Caso                                    | Resultado                                     |
|-----------------------------------------|-----------------------------------------------|
| Nada validado                           | Todo a 0, tras 0                              |
| Par 4, recibe 1, hace 5                 | 2 pts netos, 1 bruto; 5 brutos, 4 netos;      |
|                                         | al par neto, +1 bruto                         |
| Plus que da 1, par 4, hace 4            | 1 punto                                       |
| Raya (Stableford)                       | 0 puntos; cuenta en «tras», no en golpes      |
| 9 en un par 4                           | 0 puntos, nunca negativos                     |
| Los 18 validados                        | Completa                                      |
"""

from decimal import Decimal

from src.modules.competition.domain.services.tarjeta_de_stroke_play import TarjetaDeStrokePlay
from src.modules.competition.domain.value_objects.jugador_de_partida import (
    JugadorDePartida,
)
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId


def _foto(
    golpes_recibidos: tuple[int, ...], pares: tuple[int, ...] = (4,) * 18
) -> JugadorDePartida:
    return JugadorDePartida(
        user_id=UserId.generate(),
        handicap=Decimal("10.0"),
        playing_handicap=sum(golpes_recibidos),
        tee_color=TeeColor.YELLOW,
        tee_gender=None,
        golpes_por_hoyo=golpes_recibidos,
        par_por_hoyo=pares,
    )


def test_nothing_validated():
    tarjeta = TarjetaDeStrokePlay.de(_foto((1,) * 18), {})

    assert (tarjeta.puntos, tarjeta.puntos_brutos, tarjeta.golpes_brutos, tarjeta.tras) == (
        0,
        0,
        0,
        0,
    )
    assert not tarjeta.completa


def test_a_hole_with_a_stroke():
    tarjeta = TarjetaDeStrokePlay.de(_foto((1,) + (0,) * 17), {1: 5})

    assert (tarjeta.puntos, tarjeta.puntos_brutos) == (2, 1)
    assert (tarjeta.golpes_brutos, tarjeta.golpes_netos) == (5, 4)
    assert (tarjeta.al_par_neto, tarjeta.al_par_bruto) == (0, 1)
    assert tarjeta.tras == 1


def test_a_plus_player_gives_a_stroke():
    tarjeta = TarjetaDeStrokePlay.de(_foto((-1,) + (0,) * 17), {1: 4})

    assert tarjeta.puntos == 1
    assert tarjeta.golpes_netos == 5


def test_a_picked_up_ball_scores_nothing_but_counts_as_played():
    tarjeta = TarjetaDeStrokePlay.de(_foto((0,) * 18), {1: None, 2: 4})

    assert tarjeta.puntos == 2
    assert tarjeta.tras == 2
    assert tarjeta.golpes_brutos == 4
    assert tarjeta.con_raya


def test_never_negative_points():
    assert TarjetaDeStrokePlay.de(_foto((0,) * 18), {1: 9}).puntos == 0


def test_eighteen_validated_is_complete():
    tarjeta = TarjetaDeStrokePlay.de(_foto((0,) * 18), dict.fromkeys(range(1, 19), 4))

    assert tarjeta.completa
    assert tarjeta.puntos == 36
    assert tarjeta.al_par_neto == 0


def test_the_par_comes_from_the_snapshot():
    """Un par 3: 3 golpes son al par, y 2 puntos (P12)."""
    tarjeta = TarjetaDeStrokePlay.de(_foto((0,) * 18, pares=(3,) + (4,) * 17), {1: 3})

    assert (tarjeta.puntos, tarjeta.al_par_bruto, tarjeta.par_jugado) == (2, 0, 3)


def test_seventeen_validated_is_not_complete():
    assert not TarjetaDeStrokePlay.de(_foto((0,) * 18), dict.fromkeys(range(1, 18), 4)).completa
