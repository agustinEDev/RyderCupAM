"""
El hándicap fijado corregido tras el cierre llega a sus partidas sin salir (#251, PR 4; G1).

| Caso                                    | Resultado                                 |
|-----------------------------------------|-------------------------------------------|
| Su fijado pasa de 2 a 20, sin salir     | Su foto, recalculada; la de los demás no  |
| Su partida ya salió                     | No se toca                                |
| Hoja nueva: 4 que juegan + 1 NP en 4    | Cabe (QA 2, 12 oct)                       |
| Hoja nueva de 3: 4 que juegan + 1 NP    | No cabe                                   |
| Otro campo: un NP sin barra en él       | No se le recalcula ni bloquea             |
"""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.modules.competition.application.exceptions import FranjaInvalidaError
from src.modules.competition.application.services.jugadores_de_la_partida import (
    JugadoresDeLaPartida,
)
from src.modules.competition.application.services.partidas_de_la_franja import (
    comprobar_que_caben_las_partidas,
    recalcular_partidas,
    recalcular_su_handicap,
)
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from tests.unit.modules.competition.application.use_cases.test_generar_partidas_use_case import (
    _Escenario,
)

pytestmark = pytest.mark.asyncio


async def _corregido(*, salida: bool):
    escenario = _Escenario()
    await escenario.guardar()
    quien, otro = await escenario.con_plaza("2.0"), await escenario.con_plaza("1.0")
    await escenario.generar()
    (partida,) = await escenario.uow.partidas.de_la_franja(escenario.manana.id)
    if salida:
        await escenario.uow.partidas.guardar(
            [
                Partida(
                    id=partida.id,
                    competition_id=partida.competition_id,
                    round_id=partida.round_id,
                    numero=partida.numero,
                    jugadores=partida.jugadores,
                    marcadores=partida.marcadores,
                    estado=EstadoPartida.IN_PROGRESS,
                )
            ]
        )
    (inscripcion,) = await escenario.uow.enrollments.find_by_user_ids_and_competition(
        [quien], escenario.competicion.id
    )
    inscripcion.congelar_handicap(Decimal("20.0"), 1)

    await recalcular_su_handicap(
        escenario.uow,
        JugadoresDeLaPartida(escenario.campos, escenario.usuarios),
        escenario.competicion,
        quien,
    )

    (despues,) = await escenario.uow.partidas.de_la_franja(escenario.manana.id)
    return partida, despues, quien, otro


def _de(partida: Partida, user_id):
    return next(j for j in partida.jugadores if j.user_id == user_id)


async def test_their_snapshot_is_redone_and_the_others_are_not():
    antes, despues, quien, otro = await _corregido(salida=False)

    assert _de(despues, quien).handicap == Decimal("20.0")
    assert _de(despues, quien).playing_handicap > _de(antes, quien).playing_handicap
    assert _de(despues, otro) == _de(antes, otro)


async def test_a_group_already_out_is_not_touched():
    antes, despues, quien, _ = await _corregido(salida=True)

    assert _de(despues, quien) == _de(antes, quien)


def _de_cinco_con_un_np() -> Partida:
    from tests.unit.modules.competition.domain.entities.test_partida import _jugador, _partida

    partida = _partida(4)
    partida.no_presentado(partida.user_ids[0])
    partida.meter(_jugador(), 4)
    return partida


def test_four_playing_and_a_no_show_fit_in_groups_of_four():
    from datetime import time

    comprobar_que_caben_las_partidas(
        [_de_cinco_con_un_np()], HojaDeSalidas(time(9), time(10), 10, 4)
    )


def test_four_playing_do_not_fit_in_groups_of_three():
    from datetime import time

    with pytest.raises(FranjaInvalidaError):
        comprobar_que_caben_las_partidas(
            [_de_cinco_con_un_np()], HojaDeSalidas(time(9), time(10), 10, 3)
        )


class _SinBarraPara:
    """Construye las fotos, pero falla si le piden la de un no presentado."""

    def __init__(self, faltan):
        self.faltan = set(faltan)
        self.pedidos = []

    async def construir(self, uow, competicion, franja, quienes):
        self.pedidos = list(quienes)
        if self.faltan & set(quienes):
            raise AssertionError("Se pidió la foto de un no presentado")
        return {u: _jugador_nuevo(u) for u in quienes}


def _jugador_nuevo(user_id):
    from tests.unit.modules.competition.domain.entities.test_partida import _jugador

    return _jugador(playing_handicap=20, user_id=user_id)


async def test_another_course_does_not_rebuild_a_no_show():
    partida = _de_cinco_con_un_np()
    falta = partida.user_ids[0]
    antes = partida.jugadores[0]
    jugadores = _SinBarraPara([falta])

    async def guardar(_):
        return None

    uow = SimpleNamespace(partidas=SimpleNamespace(guardar=guardar))
    await recalcular_partidas(uow, jugadores, None, None, [partida])

    assert falta not in jugadores.pedidos
    assert partida.jugadores[0] == antes
    assert {j.playing_handicap for j in partida.jugadores[1:]} == {20}
