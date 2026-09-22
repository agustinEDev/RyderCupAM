"""
Tests de GetCompetitionUseCase.tiene_equipos (FE #692).

La ficha tiene que saber si ya hay equipos repartidos para ofrecer el botón
correcto. Con equipos, los capitanes ya no se cambian, y una competición
reabierta solo se vuelve a cerrar con «Cerrar inscripciones»: reabrir no deshace
el reparto. Lo decide el servidor, como `can_delete`.
"""

from uuid import uuid4

import pytest

from src.modules.competition.application.use_cases.get_competition_use_case import (
    GetCompetitionUseCase,
)
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.helpers import create_competition

pytestmark = pytest.mark.asyncio


async def test_sin_reparto_no_tiene_equipos():
    """
    Given: una competición recién creada
    When: se pregunta si tiene equipos
    Then: no
    """
    uow = InMemoryUnitOfWork()
    creada = await create_competition(uow, UserId(uuid4()))

    assert await GetCompetitionUseCase(uow).tiene_equipos(CompetitionId(creada.id)) is False


async def test_con_reparto_tiene_equipos():
    """
    Given: una competición con los equipos repartidos
    When: se pregunta si tiene equipos
    Then: sí
    """
    uow = InMemoryUnitOfWork()
    creada = await create_competition(uow, UserId(uuid4()))
    async with uow:
        await uow.team_assignments.add(
            TeamAssignment.create(
                competition_id=CompetitionId(creada.id),
                mode=TeamAssignmentMode.MANUAL,
                team_a_player_ids=[UserId(uuid4())],
                team_b_player_ids=[UserId(uuid4())],
            )
        )
        await uow.commit()

    assert await GetCompetitionUseCase(uow).tiene_equipos(CompetitionId(creada.id)) is True


async def test_el_reparto_de_otra_competicion_no_cuenta():
    """
    Given: dos competiciones y solo la primera con reparto
    When: se pregunta por la segunda
    Then: no tiene equipos
    """
    uow = InMemoryUnitOfWork()
    # Cada una de un organizador: el nombre no se puede repetir para el mismo
    primera = await create_competition(uow, UserId(uuid4()))
    segunda = await create_competition(uow, UserId(uuid4()))
    async with uow:
        await uow.team_assignments.add(
            TeamAssignment.create(
                competition_id=CompetitionId(primera.id),
                mode=TeamAssignmentMode.MANUAL,
                team_a_player_ids=[UserId(uuid4())],
                team_b_player_ids=[UserId(uuid4())],
            )
        )
        await uow.commit()

    assert await GetCompetitionUseCase(uow).tiene_equipos(CompetitionId(segunda.id)) is False
