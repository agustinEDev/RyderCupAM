"""
El hándicap fijado corregido tras el cierre llega a sus partidas sin salir (#251, PR 4; G1).

| Caso                                    | Resultado                                 |
|-----------------------------------------|-------------------------------------------|
| Su fijado pasa de 2 a 20, sin salir     | Su foto, recalculada; la de los demás no  |
| Su partida ya salió                     | No se toca                                |
"""

from decimal import Decimal

import pytest

from src.modules.competition.application.services.jugadores_de_la_partida import (
    JugadoresDeLaPartida,
)
from src.modules.competition.application.services.partidas_de_la_franja import (
    recalcular_su_handicap,
)
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
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
