"""Que invitaciones ya no se pueden aceptar, segun competicion (revision final, 22 oct)."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryCompetitionUnitOfWork,
)
from src.modules.social.infrastructure.adapters.invitation_availability_adapter import (
    InvitationAvailabilityAdapter,
)
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio

AHORA = datetime(2026, 10, 22, 12, 0)


async def _invitacion(uow, status: InvitationStatus, caduca: datetime) -> str:
    invitacion = Invitation.reconstruct(
        id=InvitationId.generate(),
        competition_id=CompetitionId(uuid4()),
        inviter_id=UserId(uuid4()),
        invitee_email="inv@test.com",
        invitee_user_id=UserId(uuid4()),
        status=status,
        expires_at=caduca,
    )
    async with uow:
        await uow.invitations.add(invitacion)
    return str(invitacion.id.value)


async def test_cerradas_las_no_pendientes_las_caducadas_y_las_que_no_existen():
    uow = InMemoryCompetitionUnitOfWork()
    abierta = await _invitacion(uow, InvitationStatus.PENDING, AHORA + timedelta(days=1))
    caducada = await _invitacion(uow, InvitationStatus.PENDING, AHORA - timedelta(seconds=1))
    justo = await _invitacion(uow, InvitationStatus.PENDING, AHORA)
    rechazada = await _invitacion(uow, InvitationStatus.DECLINED, AHORA + timedelta(days=1))
    sin_plaza = await _invitacion(uow, InvitationStatus.NO_ROOM, AHORA + timedelta(days=1))
    no_existe = str(uuid4())

    cerradas = await InvitationAvailabilityAdapter(uow, reloj=lambda: AHORA).closed_ids(
        [abierta, caducada, justo, rechazada, sin_plaza, no_existe, "ilegible"]
    )

    assert cerradas == {caducada, justo, rechazada, sin_plaza, no_existe, "ilegible"}


async def test_no_carga_las_invitaciones_una_a_una():
    uow = InMemoryCompetitionUnitOfWork()
    abierta = await _invitacion(uow, InvitationStatus.PENDING, AHORA + timedelta(days=1))

    async def _prohibido(*_args, **_kwargs):
        raise AssertionError("una lectura por invitacion")

    uow.invitations.find_by_id = _prohibido

    adaptador = InvitationAvailabilityAdapter(uow, reloj=lambda: AHORA)
    assert await adaptador.closed_ids([abierta]) == set()


async def test_sin_ids_no_lee_nada():
    adaptador = InvitationAvailabilityAdapter(InMemoryCompetitionUnitOfWork())
    assert await adaptador.closed_ids([]) == set()
