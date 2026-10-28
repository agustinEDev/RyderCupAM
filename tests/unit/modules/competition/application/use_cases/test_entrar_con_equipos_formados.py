"""
Entrar con los equipos formados ya no los deshace (release social 3, T1, 28 oct 2026).

Los equipos se forman con las inscripciones cerradas; al reabrirlas siguen ahí.
Quien entra entonces (aprobado, invitado que acepta o inscrito a mano) queda sin
equipo y el organizador le pone en uno; el reparto de los demás se queda.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.enrollment_dto import (
    DirectEnrollPlayerRequestDTO,
    HandleEnrollmentRequestDTO,
)
from src.modules.competition.application.dto.invitation_dto import RespondInvitationRequestDTO
from src.modules.competition.application.use_cases.direct_enroll_player_use_case import (
    DirectEnrollPlayerUseCase,
)
from src.modules.competition.application.use_cases.handle_enrollment_use_case import (
    HandleEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.respond_to_invitation_use_case import (
    RespondToInvitationUseCase,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UsuariosEnMemoria,
)
from src.shared.domain.value_objects.gender import Gender
from tests.unit.modules.competition.application.use_cases.equipos_formados import _montar

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
    """Si el reparto se deshizo (antes del 28 oct 2026, lo que pasaba al entrar)."""
    async with uow:
        return await uow.team_assignments.find_by_competition(comp_id) is None


async def test_inscrito_a_mano():
    uow, comp_id, organizador = await _reabierta()

    await DirectEnrollPlayerUseCase(uow, _Usuarios()).execute(
        DirectEnrollPlayerRequestDTO(competition_id=comp_id.value, user_id=uuid4()), organizador
    )

    assert not await _sin_equipos(uow, comp_id)


async def test_solicitud_aprobada():
    uow, comp_id, organizador = await _reabierta()
    solicitud = Enrollment.request(EnrollmentId.generate(), comp_id, UserId(uuid4()))
    async with uow:
        await uow.enrollments.add(solicitud)

    await HandleEnrollmentUseCase(uow, _Usuarios()).execute(
        HandleEnrollmentRequestDTO(enrollment_id=solicitud.id.value, action="APPROVE"), organizador
    )

    assert not await _sin_equipos(uow, comp_id)


async def test_solicitud_rechazada_no():
    uow, comp_id, organizador = await _reabierta()
    solicitud = Enrollment.request(EnrollmentId.generate(), comp_id, UserId(uuid4()))
    async with uow:
        await uow.enrollments.add(solicitud)

    await HandleEnrollmentUseCase(uow, _Usuarios()).execute(
        HandleEnrollmentRequestDTO(enrollment_id=solicitud.id.value, action="REJECT"), organizador
    )

    assert not await _sin_equipos(uow, comp_id)


async def test_invitacion_aceptada():
    uow, comp_id, organizador = await _reabierta()
    usuarios = UsuariosEnMemoria()
    invitado = User.create(
        first_name="Eva",
        last_name="Gil",
        email_str=f"eva_{uuid4().hex[:6]}@example.com",
        plain_password="SecureP@ssw0rd123",
        gender=Gender.FEMALE,
    )
    async with usuarios:
        await usuarios.users.save(invitado)
    invitacion = Invitation.create(
        id=InvitationId.generate(),
        competition_id=comp_id,
        inviter_id=organizador,
        invitee_email=str(invitado.email),
        invitee_user_id=invitado.id,
    )
    async with uow:
        await uow.invitations.add(invitacion)

    await RespondToInvitationUseCase(uow, usuarios).execute(
        RespondInvitationRequestDTO(
            invitation_id=invitacion.id.value, user_id=invitado.id.value, action="ACCEPT"
        )
    )

    assert not await _sin_equipos(uow, comp_id)
