"""
Borrar una franja con partidas (#251, PR 5).

| Caso                                    | Resultado                                |
|-----------------------------------------|------------------------------------------|
| Partidas generadas, nadie con plaza     | Se borra, y sus partidas con ella        |
| Con un golpe apuntado                   | RoundNotModifiableError: lo jugado queda |
"""

import pytest

from src.modules.competition.application.dto.round_match_dto import DeleteRoundRequestDTO
from src.modules.competition.application.exceptions import RoundNotModifiableError
from src.modules.competition.application.use_cases.delete_round_use_case import (
    DeleteRoundUseCase,
)
from src.modules.competition.domain.entities.golpe_de_partida import GolpeDePartida
from tests.unit.modules.competition.application.use_cases.test_anotar_hoyo_de_partida_use_case import (
    A_LAS_NUEVE_Y_CINCO,
    _partida,
)

pytestmark = pytest.mark.asyncio


async def _sin_plazas(escenario):
    for plaza in await escenario.uow.plazas.de_la_franja(escenario.manana.id):
        await escenario.uow.plazas.quitar(plaza.round_id, plaza.user_id)


async def _borrar(escenario):
    await DeleteRoundUseCase(escenario.uow).execute(
        DeleteRoundRequestDTO(round_id=escenario.manana.id.value), escenario.creador
    )


async def test_its_groups_go_with_it():
    escenario, _ = await _partida()
    await _sin_plazas(escenario)

    await _borrar(escenario)

    assert await escenario.uow.partidas.de_la_franja(escenario.manana.id) == []


async def test_a_score_entered_keeps_it():
    escenario, partida = await _partida()
    a = partida.user_ids[0]
    golpe = GolpeDePartida.crear(
        partida.id, partida.round_id, partida.competition_id, a, 1, A_LAS_NUEVE_Y_CINCO
    )
    golpe.anotar_propio(4, True, a, A_LAS_NUEVE_Y_CINCO)
    await escenario.uow.golpes_de_partida.guardar(golpe)
    await _sin_plazas(escenario)

    with pytest.raises(RoundNotModifiableError):
        await _borrar(escenario)
