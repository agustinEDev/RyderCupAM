"""
Las clasificaciones de un stroke play (#251, PR 5; decisión 4 y P5-P8, P13, P14).

Sin desempate automático: los empatados comparten puesto («T3») y, dentro del
empate, se pintan por hándicap (P5).

| Caso                                                     | Resultado                       |
|----------------------------------------------------------|---------------------------------|
| Stableford neto: A 20, B 18, C 20 (C, menos hándicap)    | C y A T1 (C delante), B 3.º     |
| Medal: -2 y +1                                           | 1.º y 2.º                       |
| Medal retirado / Stableford retirado                     | NR sin puesto / cuenta lo jugado|
| Stableford retirado sin ningún hoyo validado             | NR sin puesto, no «sin empezar» |
| «Tras» en la general: jornada vieja sin cerrar y la de hoy| El de la última en juego con    |
|                                                          | hoyos; si no hay, el máximo     |
| Sin hoyos validados / no presentado                      | Al final, sin puesto            |
| Scratch de Stableford / de Medal                          | Puntos / golpes brutos (P13)    |
| Scratch con categoría                                    | Error: no tiene                 |
| Filtro de categoría                                      | Puestos dentro de ella          |
| Acumulado Stableford                                     | Suma de tarjetas                |
| Acumulado Medal                                          | Más tarjetas delante (P7); NR   |
|                                                          | en una = NR                     |
| Mejor tarjeta: entregada 30, viva 25 / viva 33           | 30 / 33 (P8)                    |
| Corte de 25 con empate en el 25.º                        | 26 visibles; la propia si fuera |
"""

from decimal import Decimal

import pytest

from src.modules.competition.domain.services.clasificacion import (
    Clasificacion,
    Escala,
    EstadoEnClasificacion,
    Participante,
    TarjetaDeJornada,
)
from src.modules.competition.domain.services.tarjeta_de_stroke_play import Tarjeta
from src.modules.competition.domain.value_objects.estado_de_tarjeta import EstadoDeTarjeta
from src.modules.competition.domain.value_objects.overall_standing import OverallStanding
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.user.domain.value_objects.user_id import UserId

STABLEFORD, MEDAL = TournamentType.STABLEFORD, TournamentType.MEDAL
ACUMULADO, MEJOR = OverallStanding.ACCUMULATED, OverallStanding.BEST_CARD
JUGANDO, ENTREGADA = EstadoDeTarjeta.JUGANDO, EstadoDeTarjeta.ENTREGADA
RETIRADO, NP = EstadoDeTarjeta.RETIRADO, EstadoDeTarjeta.NO_PRESENTADO


def _tarjeta(
    puntos: int = 0,
    al_par: int = 0,
    tras: int = 18,
    estado: EstadoDeTarjeta = ENTREGADA,
    brutos: int | None = None,
    al_par_bruto: int | None = None,
) -> TarjetaDeJornada:
    par = 4 * tras
    return TarjetaDeJornada(
        Tarjeta(
            puntos=puntos,
            puntos_brutos=puntos if brutos is None else brutos,
            golpes_brutos=par + (al_par if al_par_bruto is None else al_par_bruto),
            golpes_netos=par + al_par,
            par_jugado=par,
            tras=tras,
            con_raya=False,
        ),
        estado,
    )


def _jugador(*tarjetas: TarjetaDeJornada, handicap="10.0", categoria=1) -> Participante:
    return Participante(UserId.generate(), Decimal(handicap), categoria, tuple(tarjetas))


def _clasificar(participantes, tipo=STABLEFORD, escala=Escala.NETA, regla=ACUMULADO, **kw):
    return Clasificacion.de(participantes, tipo, escala, regla, **kw)


def _puestos(filas, participantes) -> list[tuple[int, int | None, bool]]:
    """(índice del participante, puesto, empatado), en el orden de las filas."""
    indice = {p.user_id: i for i, p in enumerate(participantes)}
    return [(indice[f.user_id], f.puesto, f.empatado) for f in filas]


def test_stableford_ties_share_the_position_and_go_by_handicap():
    a = _jugador(_tarjeta(20), handicap="12.0")
    b = _jugador(_tarjeta(18))
    c = _jugador(_tarjeta(20), handicap="5.0")

    filas = _clasificar([a, b, c])

    assert _puestos(filas, [a, b, c]) == [(2, 1, True), (0, 1, True), (1, 3, False)]
    assert [f.valor for f in filas] == [20, 20, 18]


def test_medal_lower_to_par_wins():
    a, b = _jugador(_tarjeta(al_par=-2)), _jugador(_tarjeta(al_par=1))

    filas = _clasificar([b, a], tipo=MEDAL)

    assert _puestos(filas, [a, b]) == [(0, 1, False), (1, 2, False)]
    assert [f.valor for f in filas] == [-2, 1]


def test_medal_retired_is_nr_and_stableford_retired_counts_what_was_played():
    medal_ret = _jugador(_tarjeta(al_par=-5, tras=9, estado=RETIRADO))
    medal = _jugador(_tarjeta(al_par=3))
    st_ret = _jugador(_tarjeta(30, tras=12, estado=RETIRADO))
    st = _jugador(_tarjeta(25))

    medal_filas = _clasificar([medal_ret, medal], tipo=MEDAL)
    st_filas = _clasificar([st_ret, st])

    assert _puestos(medal_filas, [medal_ret, medal]) == [(1, 1, False), (0, None, False)]
    assert medal_filas[1].estado == EstadoEnClasificacion.NR
    assert _puestos(st_filas, [st_ret, st]) == [(0, 1, False), (1, 2, False)]


@pytest.mark.parametrize("regla", [ACUMULADO, MEJOR])
def test_stableford_retired_without_any_hole_is_nr(regla):
    # Salía «sin empezar», como si aún fuera a salir
    retirado = _jugador(_tarjeta(0, tras=0, estado=RETIRADO))
    st = _jugador(_tarjeta(25))

    filas = _clasificar([retirado, st], regla=regla)

    assert [(f.puesto, f.estado) for f in filas] == [
        (1, EstadoEnClasificacion.CLASIFICADO),
        (None, EstadoEnClasificacion.NR),
    ]


def test_not_started_and_no_show_go_last_without_position():
    jugando = _jugador(_tarjeta(10, tras=5, estado=JUGANDO))
    sin_empezar = _jugador(_tarjeta(0, tras=0, estado=JUGANDO))
    no_presentado = _jugador(_tarjeta(0, tras=0, estado=NP))

    filas = _clasificar([no_presentado, sin_empezar, jugando])

    assert [(f.puesto, f.estado) for f in filas] == [
        (1, EstadoEnClasificacion.CLASIFICADO),
        (None, EstadoEnClasificacion.SIN_EMPEZAR),
        (None, EstadoEnClasificacion.NP),
    ]
    assert filas[0].tras == 5


@pytest.mark.parametrize(
    ("tarjetas", "tras"),
    [
        # Ayer sin cerrar con 17 y hoy por el 5: va por el 5
        ((_tarjeta(30, tras=17, estado=JUGANDO), _tarjeta(8, tras=5, estado=JUGANDO)), 5),
        # Ayer entregada y mañana aún sin salir: no «tras 0»
        ((_tarjeta(30), _tarjeta(0, tras=0, estado=JUGANDO)), 18),
    ],
)
def test_thru_comes_from_the_last_live_card_with_holes(tarjetas, tras):
    """Las tarjetas llegan por calendario."""
    (fila,) = _clasificar([_jugador(*tarjetas)])

    assert fila.tras == tras


def test_stableford_scratch_uses_gross_points():
    a = _jugador(_tarjeta(40, brutos=20))
    b = _jugador(_tarjeta(36, brutos=25))

    filas = _clasificar([a, b], escala=Escala.SCRATCH)

    assert _puestos(filas, [a, b]) == [(1, 1, False), (0, 2, False)]
    assert filas[0].valor == 25


def test_medal_scratch_uses_gross_strokes():
    a = _jugador(_tarjeta(al_par=-4, al_par_bruto=8))
    b = _jugador(_tarjeta(al_par=0, al_par_bruto=2))

    filas = _clasificar([a, b], tipo=MEDAL, escala=Escala.SCRATCH)

    assert _puestos(filas, [a, b]) == [(1, 1, False), (0, 2, False)]


def test_the_scratch_has_no_categories():
    with pytest.raises(ValueError):
        _clasificar([_jugador(_tarjeta(10))], escala=Escala.SCRATCH, categoria=1)


def test_a_category_is_its_own_classification():
    primera = _jugador(_tarjeta(30), categoria=1)
    segunda_a = _jugador(_tarjeta(20), categoria=2)
    segunda_b = _jugador(_tarjeta(25), categoria=2)

    filas = _clasificar([primera, segunda_a, segunda_b], categoria=2)

    assert _puestos(filas, [primera, segunda_a, segunda_b]) == [(2, 1, False), (1, 2, False)]


def test_accumulated_stableford_adds_the_cards():
    a = _jugador(_tarjeta(30), _tarjeta(20))
    b = _jugador(_tarjeta(36))

    filas = _clasificar([b, a])

    assert [f.valor for f in filas] == [50, 36]
    assert filas[0].tarjetas == 2


def test_accumulated_medal_more_cards_first_and_one_nr_makes_it_nr():
    dos = _jugador(_tarjeta(al_par=5), _tarjeta(al_par=4))
    una = _jugador(_tarjeta(al_par=-3))
    con_nr = _jugador(_tarjeta(al_par=0), _tarjeta(al_par=-1, tras=10, estado=RETIRADO))

    filas = _clasificar([una, con_nr, dos], tipo=MEDAL)

    assert _puestos(filas, [dos, una, con_nr]) == [(0, 1, False), (1, 2, False), (2, None, False)]
    assert filas[0].valor == 9


@pytest.mark.parametrize(("viva", "esperado"), [(25, 30), (33, 33)])
def test_best_card_the_best_closed_or_the_live_one_if_better(viva, esperado):
    jugador = _jugador(_tarjeta(30), _tarjeta(viva, tras=14, estado=JUGANDO))

    (fila,) = _clasificar([jugador], regla=MEJOR)

    assert fila.valor == esperado


def test_best_card_in_medal_is_the_lowest():
    jugador = _jugador(_tarjeta(al_par=4), _tarjeta(al_par=-1))

    (fila,) = _clasificar([jugador], tipo=MEDAL, regla=MEJOR)

    assert fila.valor == -1


class TestCorte:
    def _veintiseis(self):
        # Del 1.º al 24.º distintos; el 25.º y el 26.º empatan; el 27.º, solo
        participantes = [_jugador(_tarjeta(100 - i)) for i in range(24)]
        participantes += [_jugador(_tarjeta(50)), _jugador(_tarjeta(50)), _jugador(_tarjeta(10))]
        return participantes, _clasificar(participantes)

    def test_ties_at_the_cut_all_get_in(self):
        _, filas = self._veintiseis()

        visibles, _ = Clasificacion.cortar(filas, 25, None)

        assert len(visibles) == 26
        assert {f.puesto for f in visibles[-2:]} == {25}

    def test_my_row_below_when_out(self):
        participantes, filas = self._veintiseis()

        _, propia = Clasificacion.cortar(filas, 25, participantes[-1].user_id)

        assert propia is not None and propia.puesto == 27

    def test_no_own_row_when_in(self):
        participantes, filas = self._veintiseis()

        assert Clasificacion.cortar(filas, 25, participantes[0].user_id)[1] is None
