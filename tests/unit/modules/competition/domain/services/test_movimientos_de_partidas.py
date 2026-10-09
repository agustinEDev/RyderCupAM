"""
Mover jugadores entre partidas y reordenarlas (#251, PR 4; D4, D13, M1-M3 del 9 oct 2026).

| Mover                                              | Resultado                              |
|----------------------------------------------------|----------------------------------------|
| A una con hueco                                    | Origen -1, destino +1                  |
| A una llena sin intercambio                        | Error                                  |
| Intercambio con uno de la llena                    | Cada uno al sitio del otro             |
| Intercambio con uno que no está en el destino      | Error                                  |
| Intercambio hacia una partida nueva                | Error                                  |
| Dejar el origen con 1 (sin intercambio)            | Error (M2)                             |
| Sacar al único de una partida                      | Desaparece y las de detrás suben (M3)  |
| A una nueva al final                               | Nace incompleta (M1)                   |
| A una nueva sin salidas libres                     | Error                                  |
| Uno sin partida a una con hueco                    | Entra                                  |
| Uno sin partida, intercambio en una llena          | El otro queda sin partida              |
| Al mismo sitio / a una de otra franja              | Error                                  |

| Reordenar                                          | Resultado                              |
|----------------------------------------------------|----------------------------------------|
| Todas, en otro orden                               | Números 1…n en ese orden               |
| Falta una, sobra una, una repetida                 | Error                                  |
"""

from datetime import time
from decimal import Decimal
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.services.movimientos_de_partidas import (
    MovimientoImposibleError,
    MovimientosDePartidas,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.jugador_de_partida import (
    JugadorDePartida,
)
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId

COMPETICION = CompetitionId(uuid4())
FRANJA = RoundId.generate()
# 9:00-9:30 cada 10': 4 salidas de 4
HOJA = HojaDeSalidas(time(9, 0), time(9, 30), 10, 4)


def _jugador() -> JugadorDePartida:
    return JugadorDePartida(UserId.generate(), Decimal("0.0"), 0, TeeColor.YELLOW, None, (0,) * 18)


def _partidas(*tamanos: int) -> list[Partida]:
    return [
        Partida.crear(COMPETICION, FRANJA, numero, [_jugador() for _ in range(tamano)])
        for numero, tamano in enumerate(tamanos, start=1)
    ]


def _mover(partidas, jugador, destino=None, intercambiar_con=None):
    return MovimientosDePartidas.mover(
        partidas,
        jugador,
        destino.id if destino else None,
        intercambiar_con,
        HOJA,
        COMPETICION,
        FRANJA,
    )


def _ids(partida: Partida) -> list[UserId]:
    return partida.user_ids


class TestMover:
    def test_to_one_with_room(self):
        p1, p2 = _partidas(4, 3)
        a = p1.jugadores[0]

        cambios = _mover([p1, p2], a, p2)

        assert a.user_id not in _ids(p1) and len(p1.jugadores) == 3
        assert _ids(p2)[-1] == a.user_id
        assert {p.id for p in cambios.guardar} == {p1.id, p2.id}
        assert cambios.crear == [] and cambios.borrar == []

    def test_to_a_full_one_without_swap(self):
        p1, p2 = _partidas(4, 4)
        with pytest.raises(MovimientoImposibleError) as error:
            _mover([p1, p2], p1.jugadores[0], p2)
        assert error.value.codigo == "GROUP_FULL"

    def test_swapping_with_one_of_the_full_one(self):
        p1, p2 = _partidas(4, 4)
        a, x = p1.jugadores[0], p2.jugadores[1]

        _mover([p1, p2], a, p2, intercambiar_con=x.user_id)

        assert x.user_id in _ids(p1) and a.user_id not in _ids(p1)
        assert a.user_id in _ids(p2) and x.user_id not in _ids(p2)

    def test_swapping_with_someone_not_in_the_destination(self):
        p1, p2, p3 = _partidas(4, 4, 4)
        with pytest.raises(MovimientoImposibleError) as error:
            _mover([p1, p2, p3], p1.jugadores[0], p2, intercambiar_con=p3.jugadores[0].user_id)
        assert error.value.codigo == "SWAP_PLAYER_NOT_IN_GROUP"

    def test_swapping_into_a_new_one(self):
        p1, p2 = _partidas(4, 4)
        with pytest.raises(MovimientoImposibleError) as error:
            _mover([p1, p2], p1.jugadores[0], None, intercambiar_con=p2.jugadores[0].user_id)
        assert error.value.codigo == "SWAP_NEEDS_GROUP"

    def test_leaving_the_origin_with_one_is_refused(self):
        p1, p2 = _partidas(2, 3)
        with pytest.raises(MovimientoImposibleError) as error:
            _mover([p1, p2], p1.jugadores[0], p2)
        assert error.value.codigo == "ORIGIN_WOULD_BE_ALONE"

    def test_taking_out_the_only_one_removes_the_group_and_the_next_ones_move_up(self):
        p1, p2, p3 = _partidas(1, 4, 3)
        a = p1.jugadores[0]

        cambios = _mover([p1, p2, p3], a, p3)

        assert cambios.borrar == [p1]
        assert (p2.numero, p3.numero) == (1, 2)
        assert _ids(p3)[-1] == a.user_id
        assert {p.id for p in cambios.guardar} == {p2.id, p3.id}

    def test_to_a_new_one_at_the_end_is_born_incomplete(self):
        p1, p2 = _partidas(4, 4)
        a = p1.jugadores[0]

        cambios = _mover([p1, p2], a, None)

        (nueva,) = cambios.crear
        assert (nueva.numero, nueva.user_ids, nueva.incompleta) == (3, [a.user_id], True)
        assert cambios.guardar == [p1]

    def test_to_a_new_one_without_free_tee_times(self):
        p1, p2, p3, p4 = _partidas(4, 4, 4, 4)
        with pytest.raises(MovimientoImposibleError) as error:
            _mover([p1, p2, p3, p4], p1.jugadores[0], None)
        assert error.value.codigo == "NO_FREE_TEE_TIME"

    def test_the_only_one_to_a_new_one_keeps_numbers_without_gaps(self):
        p1, p2 = _partidas(1, 4)
        a = p1.jugadores[0]

        cambios = _mover([p1, p2], a, None)

        assert cambios.borrar == [p1]
        assert p2.numero == 1
        assert cambios.crear[0].numero == 2

    def test_someone_without_a_group_into_one_with_room(self):
        p1, p2 = _partidas(4, 3)
        nuevo = _jugador()

        cambios = _mover([p1, p2], nuevo, p2)

        assert _ids(p2)[-1] == nuevo.user_id
        assert cambios.guardar == [p2]

    def test_someone_without_a_group_swapping_leaves_the_other_without_one(self):
        p1, p2 = _partidas(4, 4)
        nuevo, x = _jugador(), p2.jugadores[0]

        cambios = _mover([p1, p2], nuevo, p2, intercambiar_con=x.user_id)

        assert nuevo.user_id in _ids(p2)
        assert all(x.user_id not in _ids(p) for p in (p1, p2))
        assert cambios.guardar == [p2]

    def test_to_the_same_group(self):
        p1, p2 = _partidas(3, 3)
        with pytest.raises(MovimientoImposibleError) as error:
            _mover([p1, p2], p1.jugadores[0], p1)
        assert error.value.codigo == "ALREADY_IN_GROUP"

    def test_to_a_group_of_another_window(self):
        p1, p2 = _partidas(3, 3)
        ajena = Partida.crear(COMPETICION, RoundId.generate(), 1, [_jugador(), _jugador()])
        with pytest.raises(MovimientoImposibleError) as error:
            MovimientosDePartidas.mover(
                [p1, p2], p1.jugadores[0], ajena.id, None, HOJA, COMPETICION, FRANJA
            )
        assert error.value.codigo == "GROUP_NOT_IN_WINDOW"


class TestReordenar:
    def test_all_of_them_in_another_order(self):
        p1, p2, p3 = _partidas(4, 4, 4)

        cambiadas = MovimientosDePartidas.reordenar([p1, p2, p3], [p3.id, p1.id, p2.id])

        assert (p3.numero, p1.numero, p2.numero) == (1, 2, 3)
        assert set(cambiadas) == {p1, p2, p3}

    @pytest.mark.parametrize(
        "orden",
        [
            pytest.param(lambda p: [p[0].id, p[1].id], id="falta una"),
            pytest.param(lambda p: [p[0].id, p[1].id, p[2].id, PartidaId.generate()], id="sobra"),
            pytest.param(lambda p: [p[0].id, p[1].id, p[2].id, p[0].id], id="todas y una repetida"),
        ],
    )
    def test_anything_but_a_permutation(self, orden):
        partidas = _partidas(4, 4, 4)
        with pytest.raises(MovimientoImposibleError) as error:
            MovimientosDePartidas.reordenar(partidas, orden(partidas))
        assert error.value.codigo == "INVALID_GROUP_ORDER"
