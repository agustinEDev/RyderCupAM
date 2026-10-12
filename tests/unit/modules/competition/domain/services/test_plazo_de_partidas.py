"""
Cuándo se pueden generar y tocar las partidas de una franja (#251, PR 4; D11 del 9 oct 2026).

Del cierre de inscripciones hasta la primera salida de la franja, y mientras no
haya salido ninguna.

| Caso                                               | Resultado            |
|----------------------------------------------------|----------------------|
| Cerrada o iniciada, antes de la primera salida     | Vale                 |
| Borrador, abierta, acabada o cancelada             | Plazo cerrado        |
| Justo a la hora de la primera salida, o después    | Plazo cerrado        |
| Alguna partida ya ha salido                        | PartidaEmpezadaError |
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.partida import Partida, PartidaEmpezadaError
from src.modules.competition.domain.services.plazo_de_partidas import (
    PlazoCerradoError,
    PlazoDePartidas,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.competition.domain.value_objects.jugador_de_partida import (
    JugadorDePartida,
)
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId

PRIMERA_SALIDA = datetime(2026, 10, 10, 7, 0, tzinfo=UTC)
ANTES = PRIMERA_SALIDA - timedelta(minutes=1)


def _partida(estado: EstadoPartida = EstadoPartida.SCHEDULED) -> Partida:
    jugadores = [
        JugadorDePartida(
            UserId.generate(), Decimal("0.0"), 0, TeeColor.YELLOW, None, (0,) * 18, (4,) * 18
        )
        for _ in range(2)
    ]
    a, b = (j.user_id for j in jugadores)
    return Partida(
        id=PartidaId.generate(),
        competition_id=CompetitionId(uuid4()),
        round_id=RoundId.generate(),
        numero=1,
        jugadores=jugadores,
        marcadores={a: b, b: a},
        estado=estado,
    )


@pytest.mark.parametrize("estado", [CompetitionStatus.CLOSED, CompetitionStatus.IN_PROGRESS])
def test_closed_or_started_before_the_first_tee_time_is_on_time(estado):
    PlazoDePartidas.comprobar(estado, PRIMERA_SALIDA, ANTES, [_partida()])


@pytest.mark.parametrize(
    "estado",
    [
        CompetitionStatus.DRAFT,
        CompetitionStatus.ACTIVE,
        CompetitionStatus.COMPLETED,
        CompetitionStatus.CANCELLED,
    ],
)
def test_any_other_competition_status_is_out_of_time(estado):
    with pytest.raises(PlazoCerradoError):
        PlazoDePartidas.comprobar(estado, PRIMERA_SALIDA, ANTES, [])


@pytest.mark.parametrize(
    "ahora", [PRIMERA_SALIDA, PRIMERA_SALIDA + timedelta(minutes=1)], ids=["a la hora", "después"]
)
def test_from_the_first_tee_time_on_is_out_of_time(ahora):
    with pytest.raises(PlazoCerradoError):
        PlazoDePartidas.comprobar(CompetitionStatus.IN_PROGRESS, PRIMERA_SALIDA, ahora, [])


def test_a_group_that_already_started_closes_it():
    with pytest.raises(PartidaEmpezadaError):
        PlazoDePartidas.comprobar(
            CompetitionStatus.IN_PROGRESS,
            PRIMERA_SALIDA,
            ANTES,
            [_partida(), _partida(EstadoPartida.IN_PROGRESS)],
        )
