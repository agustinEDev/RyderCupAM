"""
Al retirarse, el jugador sale de sus partidas sin salir (#251, PR 4; D2 del 9 oct 2026).

| Retirada                                   | Resultado                                  |
|--------------------------------------------|--------------------------------------------|
| Competición cerrada                        | Sale de la partida y suelta la plaza       |
| Iniciada, su partida sin salir             | Sale de la partida, conserva la plaza (D2) |
| Su partida ya salió                        | Se queda                                   |
| Era el único de su partida                 | Desaparece y las de detrás suben           |
"""

import pytest

from src.modules.competition.application.dto.enrollment_dto import WithdrawEnrollmentRequestDTO
from src.modules.competition.application.use_cases.withdraw_enrollment_use_case import (
    WithdrawEnrollmentUseCase,
)
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.test_generar_partidas_use_case import (
    _Escenario,
)

pytestmark = pytest.mark.asyncio


async def _generadas(*handicaps: str, status=CompetitionStatus.CLOSED):
    escenario = _Escenario()
    await escenario.guardar()
    jugadores = [await escenario.con_plaza(h) for h in handicaps]
    await escenario.generar()
    escenario.competicion._status = status
    return escenario, jugadores


async def _retirar(escenario: _Escenario, jugador: UserId) -> None:
    (inscripcion,) = await escenario.uow.enrollments.find_by_user_ids_and_competition(
        [jugador], escenario.competicion.id
    )
    await WithdrawEnrollmentUseCase(escenario.uow).execute(
        WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), jugador
    )


async def _partidas(escenario: _Escenario) -> list[Partida]:
    return await escenario.uow.partidas.de_la_franja(escenario.manana.id)


async def _tiene_plaza(escenario: _Escenario, jugador: UserId) -> bool:
    return jugador in {
        p.user_id for p in await escenario.uow.plazas.de_la_franja(escenario.manana.id)
    }


async def test_closed_leaves_the_group_and_the_place():
    escenario, jugadores = await _generadas("4.0", "3.0", "2.0", "1.0")

    await _retirar(escenario, jugadores[0])

    (partida,) = await _partidas(escenario)
    assert jugadores[0] not in partida.user_ids and len(partida.user_ids) == 3
    assert not await _tiene_plaza(escenario, jugadores[0])


async def test_started_leaves_the_group_and_keeps_the_place():
    escenario, jugadores = await _generadas(
        "4.0", "3.0", "2.0", "1.0", status=CompetitionStatus.IN_PROGRESS
    )

    await _retirar(escenario, jugadores[0])

    (partida,) = await _partidas(escenario)
    assert jugadores[0] not in partida.user_ids
    assert await _tiene_plaza(escenario, jugadores[0])


async def test_a_group_already_out_keeps_them():
    escenario, jugadores = await _generadas(
        "4.0", "3.0", "2.0", "1.0", status=CompetitionStatus.IN_PROGRESS
    )
    (partida,) = await _partidas(escenario)
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

    await _retirar(escenario, jugadores[0])

    assert jugadores[0] in (await _partidas(escenario))[0].user_ids


async def test_the_only_one_of_a_group_removes_it_and_the_next_ones_move_up():
    escenario, _ = await _generadas("5.0", "4.0", "3.0", "2.0", "1.0")
    a, b, c, d, e = (j for p in await _partidas(escenario) for j in p.jugadores)
    montadas = [
        Partida.crear(escenario.competicion.id, escenario.manana.id, numero, grupo)
        for numero, grupo in enumerate([[a], [b, c], [d, e]], start=1)
    ]
    await escenario.uow.partidas.reemplazar_franja(escenario.manana.id, montadas)

    await _retirar(escenario, a.user_id)

    assert [(p.numero, p.user_ids) for p in await _partidas(escenario)] == [
        (1, [b.user_id, c.user_id]),
        (2, [d.user_id, e.user_id]),
    ]
