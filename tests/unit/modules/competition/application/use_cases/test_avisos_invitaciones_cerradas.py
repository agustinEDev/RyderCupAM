"""
Una invitacion que se cierra sola retira su aviso de invitado (Agustin, 22 oct
2026, revision de la release social).

Todos los sitios donde una invitacion deja de estar pendiente sin que respondan
el invitado ni el organizador, y se guarda:

| Donde                                                | Pasa a    | Aviso                         |
|------------------------------------------------------|-----------|-------------------------------|
| Aceptar con la inscripcion ya cerrada                | NO_ROOM   | Se retira aunque salte error  |
| Responder una caducada                               | EXPIRED   | Se retira aunque salte error  |
| Retirar una caducada (organizador)                   | EXPIRED   | Se retira aunque salte error  |
| Listar las de la competicion (organizador)           | EXPIRED   | Se retira                     |
| Cerrar la inscripcion a mano                         | NO_ROOM   | Se retira                     |
| Nombrar capitanes (cierra la inscripcion)            | NO_ROOM   | Se retira                     |
| Ocupar la ultima plaza: aceptar, aprobar, inscribir  | NO_ROOM   | Se retira (las demas)         |
| Invitado sin cuenta                                  | -         | No hubo aviso: nada           |
| El feed caido                                        | -         | La accion sigue (WARNING)     |
"""

import logging
from datetime import datetime, timedelta

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CloseEnrollmentsRequestDTO,
    NameCaptainsRequestDTO,
)
from src.modules.competition.application.dto.enrollment_dto import (
    DirectEnrollPlayerRequestDTO,
    HandleEnrollmentRequestDTO,
)
from src.modules.competition.application.dto.invitation_dto import RespondInvitationRequestDTO
from src.modules.competition.application.use_cases.cancel_invitation_use_case import (
    CancelInvitationUseCase,
)
from src.modules.competition.application.use_cases.close_enrollments_use_case import (
    CloseEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.direct_enroll_player_use_case import (
    DirectEnrollPlayerUseCase,
)
from src.modules.competition.application.use_cases.handle_enrollment_use_case import (
    HandleEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.list_competition_invitations_use_case import (
    ListCompetitionInvitationsUseCase,
)
from src.modules.competition.application.use_cases.name_captains_use_case import (
    NameCaptainsUseCase,
)
from src.modules.competition.application.use_cases.respond_to_invitation_use_case import (
    RespondToInvitationUseCase,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.exceptions.competition_violations import (
    InvalidInvitationStatusViolation,
    InvitationNoRoomViolation,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as CompetitionInMemoryUoW,
)
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UserInMemoryUoW,
)
from tests.unit.modules.competition.application.use_cases.helpers import (
    create_approved_enrollment,
    set_competition_status,
)
from tests.unit.modules.competition.application.use_cases.test_avisos_de_actividad import (
    _Registro,
    _Roto,
)
from tests.unit.modules.competition.application.use_cases.test_invitation_capacity_and_withdraw import (
    _competicion,
    _estado,
    _pendiente,
    _usuario,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def comp_uow():
    return CompetitionInMemoryUoW()


@pytest.fixture
def user_uow():
    return UserInMemoryUoW()


@pytest.fixture
def registro():
    return _Registro()


def _cerradas(registro) -> list:
    return [a for a in registro.avisos if a[0] == "invitations_closed"]


async def _caducada(comp_uow, competicion_id, creador, invitado) -> Invitation:
    caducada = Invitation.reconstruct(
        id=InvitationId.generate(),
        competition_id=CompetitionId(competicion_id),
        inviter_id=creador.id,
        invitee_email=str(invitado.email),
        invitee_user_id=invitado.id,
        status=InvitationStatus.PENDING,
        expires_at=datetime.now() - timedelta(days=1),
    )
    async with comp_uow:
        await comp_uow.invitations.add(caducada)
    return caducada


async def _sin_cuenta(comp_uow, competicion_id, creador) -> Invitation:
    invitacion = Invitation.create(
        id=InvitationId.generate(),
        competition_id=CompetitionId(competicion_id),
        inviter_id=creador.id,
        invitee_email="nadie@test.com",
    )
    async with comp_uow:
        await comp_uow.invitations.add(invitacion)
    return invitacion


def _responde(comp_uow, user_uow, actividad, invitacion, quien, accion="ACCEPT"):
    return RespondToInvitationUseCase(comp_uow, user_uow, actividad=actividad).execute(
        RespondInvitationRequestDTO(
            invitation_id=invitacion.id.value, user_id=quien.id.value, action=accion
        )
    )


class TestAlResponder:
    async def test_aceptar_sin_plaza_la_cierra_y_retira_su_aviso(
        self, comp_uow, user_uow, registro
    ):
        """Con la inscripcion cerrada, pasa a NO_ROOM, se guarda y se avisa; luego el error."""
        creador = await _usuario(user_uow, "creador@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        invitacion = await _pendiente(comp_uow, comp.id, creador, invitado)
        await set_competition_status(comp_uow, comp.id, "CLOSED")

        with pytest.raises(InvitationNoRoomViolation):
            await _responde(comp_uow, user_uow, registro, invitacion, invitado)

        assert await _estado(comp_uow, invitacion) == InvitationStatus.NO_ROOM
        assert _cerradas(registro) == [("invitations_closed", [(invitacion.id, invitado.id)])]

    async def test_responder_una_caducada_la_cierra_y_retira_su_aviso(
        self, comp_uow, user_uow, registro
    ):
        creador = await _usuario(user_uow, "creador@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        caducada = await _caducada(comp_uow, comp.id, creador, invitado)

        with pytest.raises(InvalidInvitationStatusViolation):
            await _responde(comp_uow, user_uow, registro, caducada, invitado, "DECLINE")

        assert await _estado(comp_uow, caducada) == InvitationStatus.EXPIRED
        assert _cerradas(registro) == [("invitations_closed", [(caducada.id, invitado.id)])]

    async def test_responder_una_ya_cerrada_no_vuelve_a_avisar(self, comp_uow, user_uow, registro):
        """Ya estaba NO_ROOM de antes: no ha cambiado nada ahora, no hay aviso."""
        creador = await _usuario(user_uow, "creador@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        invitacion = await _pendiente(comp_uow, comp.id, creador, invitado)
        invitacion.reject_for_no_room()
        async with comp_uow:
            await comp_uow.invitations.update(invitacion)

        with pytest.raises(InvitationNoRoomViolation):
            await _responde(comp_uow, user_uow, registro, invitacion, invitado)

        assert _cerradas(registro) == []

    async def test_aceptar_la_ultima_plaza_cierra_las_demas(self, comp_uow, user_uow, registro):
        creador = await _usuario(user_uow, "creador@test.com")
        primero = await _usuario(user_uow, "primero@test.com")
        tarde = await _usuario(user_uow, "tarde@test.com")
        comp = await _competicion(comp_uow, creador, plazas=2)
        la_primera = await _pendiente(comp_uow, comp.id, creador, primero)
        la_tardia = await _pendiente(comp_uow, comp.id, creador, tarde)

        await _responde(comp_uow, user_uow, registro, la_primera, primero)

        assert _cerradas(registro) == [("invitations_closed", [(la_tardia.id, tarde.id)])]

    async def test_el_feed_caido_no_cambia_el_error_ni_el_estado(self, comp_uow, user_uow, caplog):
        creador = await _usuario(user_uow, "creador@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        invitacion = await _pendiente(comp_uow, comp.id, creador, invitado)
        await set_competition_status(comp_uow, comp.id, "CLOSED")

        with caplog.at_level(logging.WARNING), pytest.raises(InvitationNoRoomViolation):
            await _responde(comp_uow, user_uow, _Roto(), invitacion, invitado)

        assert await _estado(comp_uow, invitacion) == InvitationStatus.NO_ROOM
        assert any(r.levelno == logging.WARNING for r in caplog.records)


class TestElOrganizador:
    async def test_retirar_una_caducada_retira_su_aviso(self, comp_uow, user_uow, registro):
        creador = await _usuario(user_uow, "creador@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        caducada = await _caducada(comp_uow, comp.id, creador, invitado)

        with pytest.raises(InvalidInvitationStatusViolation):
            await CancelInvitationUseCase(comp_uow, actividad=registro).execute(
                caducada.id.value, creador.id.value
            )

        assert _cerradas(registro) == [("invitations_closed", [(caducada.id, invitado.id)])]

    async def test_listar_las_caducadas_retira_sus_avisos(self, comp_uow, user_uow, registro):
        creador = await _usuario(user_uow, "creador@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        otro = await _usuario(user_uow, "otro@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        caducada = await _caducada(comp_uow, comp.id, creador, invitado)
        await _pendiente(comp_uow, comp.id, creador, otro)

        await ListCompetitionInvitationsUseCase(comp_uow, user_uow, actividad=registro).execute(
            str(comp.id), str(creador.id.value)
        )

        assert _cerradas(registro) == [("invitations_closed", [(caducada.id, invitado.id)])]

    async def test_cerrar_la_inscripcion_retira_los_avisos_de_las_pendientes(
        self, comp_uow, user_uow, registro
    ):
        creador = await _usuario(user_uow, "creador@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        invitacion = await _pendiente(comp_uow, comp.id, creador, invitado)
        # Sin cuenta: no hubo aviso que retirar
        await _sin_cuenta(comp_uow, comp.id, creador)
        await create_approved_enrollment(
            comp_uow, comp.id, (await _usuario(user_uow, "b@t.com")).id
        )

        await CloseEnrollmentsUseCase(comp_uow, actividad=registro).execute(
            CloseEnrollmentsRequestDTO(competition_id=comp.id), creador.id
        )

        assert _cerradas(registro) == [("invitations_closed", [(invitacion.id, invitado.id)])]

    async def test_nombrar_capitanes_retira_los_avisos_de_las_pendientes(
        self, comp_uow, user_uow, registro
    ):
        creador = await _usuario(user_uow, "creador@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        jugadores = [(await _usuario(user_uow, f"j{i}@test.com")).id for i in range(3)]
        for jugador in jugadores:
            await create_approved_enrollment(comp_uow, comp.id, jugador)
        invitacion = await _pendiente(comp_uow, comp.id, creador, invitado)

        await NameCaptainsUseCase(comp_uow, actividad=registro).execute(
            NameCaptainsRequestDTO(
                competition_id=comp.id,
                team_a_captain_id=jugadores[0].value,
                team_b_captain_id=jugadores[1].value,
            ),
            creador.id,
        )

        assert _cerradas(registro) == [("invitations_closed", [(invitacion.id, invitado.id)])]

    async def test_aprobar_la_ultima_plaza_retira_los_avisos(self, comp_uow, user_uow, registro):
        creador = await _usuario(user_uow, "creador@test.com")
        pide = await _usuario(user_uow, "pide@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=2)
        solicitud = Enrollment.request(EnrollmentId.generate(), CompetitionId(comp.id), pide.id)
        async with comp_uow:
            await comp_uow.enrollments.add(solicitud)
        invitacion = await _pendiente(comp_uow, comp.id, creador, invitado)

        await HandleEnrollmentUseCase(comp_uow, user_uow.users, actividad=registro).execute(
            HandleEnrollmentRequestDTO(enrollment_id=solicitud.id.value, action="APPROVE"),
            creador.id,
        )

        assert _cerradas(registro) == [("invitations_closed", [(invitacion.id, invitado.id)])]

    async def test_inscribir_en_la_ultima_plaza_retira_los_avisos(
        self, comp_uow, user_uow, registro
    ):
        creador = await _usuario(user_uow, "creador@test.com")
        directo = await _usuario(user_uow, "directo@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=2)
        invitacion = await _pendiente(comp_uow, comp.id, creador, invitado)

        await DirectEnrollPlayerUseCase(comp_uow, user_uow.users, actividad=registro).execute(
            DirectEnrollPlayerRequestDTO(competition_id=comp.id, user_id=directo.id.value),
            creador.id,
        )

        assert _cerradas(registro) == [("invitations_closed", [(invitacion.id, invitado.id)])]

    async def test_sin_llenarse_no_hay_aviso(self, comp_uow, user_uow, registro):
        creador = await _usuario(user_uow, "creador@test.com")
        directo = await _usuario(user_uow, "directo@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=4)
        await _pendiente(comp_uow, comp.id, creador, invitado)

        await DirectEnrollPlayerUseCase(comp_uow, user_uow.users, actividad=registro).execute(
            DirectEnrollPlayerRequestDTO(competition_id=comp.id, user_id=directo.id.value),
            creador.id,
        )

        assert _cerradas(registro) == []
