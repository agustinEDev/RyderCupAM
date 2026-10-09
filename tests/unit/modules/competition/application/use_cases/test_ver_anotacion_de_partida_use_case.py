"""
La partida para anotar y las tarjetas de los suyos (#251, PR 5; pestañas 1 y 3).

| Caso                              | Resultado                                            |
|-----------------------------------|------------------------------------------------------|
| Recién generada                   | 18 hoyos vacíos, la hora de apertura, a quién marco |
| Tras anotar                       | Cada lado, su estado; totales solo de lo validado    |
| Una tarjeta entregada             | Su estado                                            |
| Medal                             | Sin levantar bola                                    |
| Una partida que no existe         | PartidaNotFoundError                                 |
"""

from uuid import uuid4

import pytest

from src.modules.competition.application.dto.scoring_dto import SubmitHoleScoreBodyDTO
from src.modules.competition.application.exceptions import PartidaNotFoundError
from src.modules.competition.application.use_cases.anotar_hoyo_de_partida_use_case import (
    AnotarHoyoDePartidaUseCase,
)
from src.modules.competition.application.use_cases.ver_anotacion_de_partida_use_case import (
    VerAnotacionDePartidaUseCase,
)
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from tests.unit.modules.competition.application.use_cases.test_anotar_hoyo_de_partida_use_case import (
    A_LAS_NUEVE_Y_CINCO,
    PRIMERA_SALIDA,
    _partida,
)

pytestmark = pytest.mark.asyncio


def _ver(escenario):
    return VerAnotacionDePartidaUseCase(
        uow=escenario.uow, zonas=escenario.zonas, user_repository=escenario.usuarios
    )


async def _anotar(escenario, partida, quien, hoyo, **body):
    body.setdefault("marked_player_id", str(partida.marcadores[quien].value))
    await AnotarHoyoDePartidaUseCase(
        uow=escenario.uow, zonas=escenario.zonas, reloj=lambda: A_LAS_NUEVE_Y_CINCO
    ).execute(partida.id.value, hoyo, SubmitHoleScoreBodyDTO(**body), quien)


async def test_a_new_group():
    escenario, partida = await _partida()
    a, b, _ = partida.user_ids

    vista = await _ver(escenario).execute(partida.id.value, a)

    assert (vista.number, vista.tee_time, vista.status) == (1, "09:00", "SCHEDULED")
    assert vista.scoring_opens_at == PRIMERA_SALIDA
    assert vista.i_mark_user_id == b.value
    assert vista.picked_up_allowed
    jugador = vista.players[0]
    assert len(jugador.holes) == 18
    assert jugador.holes[0].status == "PENDING"
    assert (jugador.totals.thru, jugador.totals.points) == (0, 0)
    assert jugador.card_status == "JUGANDO"
    assert jugador.name


async def test_after_scoring_only_the_validated_count():
    escenario, partida = await _partida()
    a, b, c = partida.user_ids
    await _anotar(escenario, partida, a, 1, own_score=4, marked_score=5)
    await _anotar(escenario, partida, b, 1, own_score=5)
    await _anotar(escenario, partida, b, 2, own_score=4)

    vista = await _ver(escenario).execute(partida.id.value, c)

    suyo = next(p for p in vista.players if p.user_id == b.value)
    assert (suyo.holes[0].own_score, suyo.holes[0].marker_score, suyo.holes[0].status) == (
        5,
        5,
        "MATCH",
    )
    assert suyo.holes[1].status == "PENDING"
    assert suyo.totals.thru == 1
    assert suyo.totals.gross == 5
    assert suyo.marked_by_user_id == a.value
    assert vista.status == "IN_PROGRESS"


async def test_a_delivered_card():
    escenario, partida = await _partida(n=2)
    a, b = partida.user_ids
    await _anotar(escenario, partida, a, 1, own_score=4)
    abierta = await escenario.uow.partidas.find_by_id(partida.id)
    abierta.entregar(a)
    await escenario.uow.partidas.guardar([abierta])

    vista = await _ver(escenario).execute(partida.id.value, b)

    assert {p.user_id: p.card_status for p in vista.players} == {
        a.value: "ENTREGADA",
        b.value: "JUGANDO",
    }


async def test_medal_does_not_allow_picking_up():
    escenario, partida = await _partida(tipo=TournamentType.MEDAL)

    vista = await _ver(escenario).execute(partida.id.value, partida.user_ids[0])

    assert (vista.tournament_type, vista.picked_up_allowed) == ("MEDAL", False)


async def test_a_group_that_does_not_exist():
    escenario, partida = await _partida()

    with pytest.raises(PartidaNotFoundError):
        await _ver(escenario).execute(uuid4(), partida.user_ids[0])
