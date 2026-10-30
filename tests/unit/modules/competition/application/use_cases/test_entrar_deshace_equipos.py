"""
Entrar con los equipos formados también los deshace (release social 2, decidido
el 27 oct 2026).

Los equipos se forman con las inscripciones cerradas; al reabrirlas siguen ahí.
Quien entra entonces (aprobado o inscrito a mano) se quedaba fuera de los dos
equipos. Sin partidos, se deshacen, como al salir. El invitado ya no acepta por
su cuenta con los equipos formados (29 oct 2026, test_equipos_formados_congelados).
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.enrollment_dto import (
    DirectEnrollPlayerRequestDTO,
    HandleEnrollmentRequestDTO,
)
from src.modules.competition.application.use_cases.direct_enroll_player_use_case import (
    DirectEnrollPlayerUseCase,
)
from src.modules.competition.application.use_cases.handle_enrollment_use_case import (
    HandleEnrollmentUseCase,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender
from tests.unit.modules.competition.application.use_cases.test_deshacer_equipos import _montar

pytestmark = pytest.mark.asyncio


class _Usuarios:
    async def find_by_id(self, user_id):
        return SimpleNamespace(id=user_id, gender=Gender.MALE, handicap=None)


async def _reabierta():
    """Equipos formados, sin partidos, y las inscripciones reabiertas."""
    uow, comp_id, _, _, _ = await _montar()
    async with uow:
        competicion = await uow.competitions.find_by_id(comp_id)
        competicion.reopen_enrollments()
        await uow.competitions.update(competicion)
        await uow.commit()
    return uow, comp_id, competicion.creator_id


async def _sin_equipos(uow, comp_id) -> bool:
    async with uow:
        return await uow.team_assignments.find_by_competition(comp_id) is None


async def test_inscrito_a_mano():
    uow, comp_id, organizador = await _reabierta()

    await DirectEnrollPlayerUseCase(uow, _Usuarios()).execute(
        DirectEnrollPlayerRequestDTO(competition_id=comp_id.value, user_id=uuid4()), organizador
    )

    assert await _sin_equipos(uow, comp_id)


async def test_solicitud_aprobada():
    uow, comp_id, organizador = await _reabierta()
    solicitud = Enrollment.request(EnrollmentId.generate(), comp_id, UserId(uuid4()))
    async with uow:
        await uow.enrollments.add(solicitud)

    await HandleEnrollmentUseCase(uow, _Usuarios()).execute(
        HandleEnrollmentRequestDTO(enrollment_id=solicitud.id.value, action="APPROVE"), organizador
    )

    assert await _sin_equipos(uow, comp_id)


async def test_solicitud_rechazada_no():
    uow, comp_id, organizador = await _reabierta()
    solicitud = Enrollment.request(EnrollmentId.generate(), comp_id, UserId(uuid4()))
    async with uow:
        await uow.enrollments.add(solicitud)

    await HandleEnrollmentUseCase(uow, _Usuarios()).execute(
        HandleEnrollmentRequestDTO(enrollment_id=solicitud.id.value, action="REJECT"), organizador
    )

    assert not await _sin_equipos(uow, comp_id)
