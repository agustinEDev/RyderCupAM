"""El repositorio en memoria de inscripciones no recorta a escondidas (BE #314)."""

from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_enrollment_repository import (
    InMemoryEnrollmentRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio


async def _con_inscritos(n: int):
    repo = InMemoryEnrollmentRepository()
    competition_id = CompetitionId(uuid4())
    for _ in range(n):
        await repo.add(
            Enrollment.direct_enroll(
                id=EnrollmentId.generate(), competition_id=competition_id, user_id=UserId.generate()
            )
        )
    return repo, competition_id


async def test_find_by_competition_returns_every_enrollment_past_one_hundred():
    """
    Given 150 inscripciones de una competición
    When se piden sin límite
    Then llegan las 150: el límite oculto de 100 dejaba fuera al resto en seis
    casos de uso, y en memoria ni siquiera se notaba
    """
    repo, competition_id = await _con_inscritos(150)

    assert len(await repo.find_by_competition(competition_id)) == 150


async def test_find_by_competition_and_status_returns_every_enrollment_past_one_hundred():
    """Given 150 aprobadas When se piden por estado Then llegan las 150."""
    repo, competition_id = await _con_inscritos(150)

    assert (
        len(await repo.find_by_competition_and_status(competition_id, EnrollmentStatus.APPROVED))
        == 150
    )


async def test_an_explicit_limit_and_offset_still_page():
    """Given 150 When se pide una página explícita Then se respeta, en los dos métodos."""
    repo, competition_id = await _con_inscritos(150)

    assert len(await repo.find_by_competition(competition_id, limit=10, offset=145)) == 5
    assert (
        len(
            await repo.find_by_competition_and_status(
                competition_id, EnrollmentStatus.APPROVED, limit=10, offset=0
            )
        )
        == 10
    )
