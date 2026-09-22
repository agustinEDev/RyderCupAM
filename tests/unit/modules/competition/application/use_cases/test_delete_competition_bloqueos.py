"""
Tests de los bloqueos del borrado de competiciones (BE #347).

Con la regla de «nada jugado», bloquear la competición ya no basta: anotar un
hoyo en un partido abierto, conceder o terminar no tocan esa fila. Entre mirar
que no hay nada jugado y borrar, un golpe anotado a la vez se iría en la
cascada. Por eso `execute` lee los partidos y las tarjetas con su fila
bloqueada: si el golpe llega antes, el borrado lo espera y lo ve; si llega
después, ya no encuentra la fila.

Aquí se comprueba QUÉ lectura usa cada camino. Que el bloqueo se tome de verdad
solo se ve contra PostgreSQL, en los tests de integración de los repositorios.
"""

from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
    DeleteCompetitionRequestDTO,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.delete_competition_use_case import (
    DeleteCompetitionUseCase,
)
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.helpers import montar_calendario

pytestmark = pytest.mark.asyncio


async def _cerrada_con_partido_abierto() -> tuple[InMemoryUnitOfWork, CompetitionId, UserId]:
    """Una cerrada con un partido abierto y sus tarjetas vacías: se puede borrar."""
    uow = InMemoryUnitOfWork()
    creator_id = UserId(uuid4())
    creada = await CreateCompetitionUseCase(uow, LocationBuilder(uow.countries)).execute(
        CreateCompetitionRequestDTO(
            name="Ryder Cup 2030",
            start_date=date(2030, 6, 1),
            end_date=date(2030, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
        ),
        creator_id,
    )
    competition_id = CompetitionId(creada.id)
    async with uow:
        competition = await uow.competitions.find_by_id(competition_id)
        competition.close_enrollments()
        await uow.competitions.update(competition)
        await uow.commit()
    await montar_calendario(uow, competition_id, "empezado")
    return uow, competition_id, creator_id


def _espiar(uow: InMemoryUnitOfWork) -> dict[str, AsyncMock]:
    """Envuelve las cuatro lecturas para saber cuáles se usan, sin cambiar lo que devuelven."""
    espias = {}
    for repo, metodo in [
        (uow.matches, "find_by_round"),
        (uow.matches, "find_by_round_for_update"),
        (uow.hole_scores, "find_by_match"),
        (uow.hole_scores, "find_by_match_for_update"),
    ]:
        espia = AsyncMock(side_effect=getattr(repo, metodo))
        setattr(repo, metodo, espia)
        espias[metodo] = espia
    return espias


async def test_borrar_lee_partidos_y_tarjetas_con_la_fila_bloqueada():
    """
    Given: una cerrada con un partido abierto y sus tarjetas vacías
    When: el creador la borra
    Then: los partidos y las tarjetas se leyeron bloqueados, y nada sin bloquear
    """
    uow, competition_id, creator_id = await _cerrada_con_partido_abierto()
    espias = _espiar(uow)

    await DeleteCompetitionUseCase(uow).execute(
        DeleteCompetitionRequestDTO(competition_id=competition_id.value), creator_id
    )

    assert espias["find_by_round_for_update"].await_count == 1
    assert espias["find_by_match_for_update"].await_count == 1
    assert espias["find_by_round"].await_count == 0
    assert espias["find_by_match"].await_count == 0


async def test_preguntar_si_se_puede_borrar_no_bloquea_nada():
    """Es una pregunta que hace cada ficha: bloquear retendría a quien está anotando."""
    uow, competition_id, creator_id = await _cerrada_con_partido_abierto()
    espias = _espiar(uow)

    dice = await DeleteCompetitionUseCase(uow).puede_borrar(competition_id, creator_id)

    assert dice is True
    assert espias["find_by_round"].await_count == 1
    assert espias["find_by_match"].await_count == 1
    assert espias["find_by_round_for_update"].await_count == 0
    assert espias["find_by_match_for_update"].await_count == 0
