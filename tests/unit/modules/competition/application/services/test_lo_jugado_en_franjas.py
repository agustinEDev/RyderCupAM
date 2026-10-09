"""
Lo jugado de un stroke play también se protege (#251, PR 5).

Un golpe apuntado en una partida es jugado: la competición no se borra y la
franja tampoco. Generar las partidas no es jugar.

| Caso                                   | Resultado |
|----------------------------------------|-----------|
| Partidas generadas, sin golpes         | No jugado |
| Un golpe apuntado (aunque sin validar) | Jugado    |
"""

import pytest

from src.modules.competition.application.services.lo_jugado import LoJugado
from src.modules.competition.domain.entities.golpe_de_partida import GolpeDePartida
from tests.unit.modules.competition.application.use_cases.test_anotar_hoyo_de_partida_use_case import (
    A_LAS_NUEVE_Y_CINCO,
    _partida,
)

pytestmark = pytest.mark.asyncio


async def test_generated_groups_are_not_played():
    escenario, _ = await _partida()

    assert not await LoJugado(escenario.uow).en_la_sesion(escenario.manana.id)
    assert not await LoJugado(escenario.uow).en_la_competicion(escenario.competicion.id)


async def test_one_score_entered_is_played():
    escenario, partida = await _partida()
    a = partida.user_ids[0]
    golpe = GolpeDePartida.crear(
        partida.id, partida.round_id, partida.competition_id, a, 1, A_LAS_NUEVE_Y_CINCO
    )
    golpe.anotar_propio(4, True, a, A_LAS_NUEVE_Y_CINCO)
    await escenario.uow.golpes_de_partida.guardar(golpe)

    assert await LoJugado(escenario.uow).en_la_sesion(escenario.manana.id)
    assert await LoJugado(escenario.uow).en_la_competicion(escenario.competicion.id, bloquear=True)
