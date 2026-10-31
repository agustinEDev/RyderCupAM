"""
Con franjas, el cupo lo marcan sus plazas en TODOS los caminos (28 oct 2026).

Apuntarse a una pública ya no miraba `max_players` en un stroke play con
franjas (D8); el revisor vio que los demás caminos sí, y que al llegar a ese
número cerraban las invitaciones pendientes «sin plaza» con las franjas aún con
sitio. Decidido: con franjas ninguno lo mira; sin franjas, como siempre.

    #    camino                                    | con franjas y max lleno
    -----|-----------------------------------------|----------------------------
    C1   el organizador inscribe a mano            | entra
    C2   el organizador aprueba una solicitud      | entra
    C3   el invitado acepta                        | entra; las demás pendientes siguen
    C4   el organizador invita                     | sale la invitación
    C5   sin franjas                               | llena, como siempre
"""

from datetime import date, time, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.enrollment_dto import (
    DirectEnrollPlayerRequestDTO,
    HandleEnrollmentRequestDTO,
)
from src.modules.competition.application.dto.invitation_dto import (
    RespondInvitationRequestDTO,
    SendInvitationByUserIdRequestDTO,
)
from src.modules.competition.application.exceptions import CompetitionFullError
from src.modules.competition.application.use_cases.direct_enroll_player_use_case import (
    DirectEnrollPlayerUseCase,
)
from src.modules.competition.application.use_cases.handle_enrollment_use_case import (
    HandleEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.respond_to_invitation_use_case import (
    RespondToInvitationUseCase,
)
from src.modules.competition.application.use_cases.send_invitation_by_user_id_use_case import (
    SendInvitationByUserIdUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UsuariosEnMemoria,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.play_mode import PlayMode

pytestmark = pytest.mark.asyncio

DIA = date.today() + timedelta(days=30)


class _E:
    async def montar(self, con_franjas: bool):
        self.uow = InMemoryUnitOfWork()
        self.usuarios = UsuariosEnMemoria()
        self.creador = await self.usuario()
        self.competicion = Competition(
            id=CompetitionId(uuid4()),
            creator_id=self.creador.id,
            name=CompetitionName("Medal de noviembre"),
            dates=DateRange(DIA, DIA),
            location=Location(CountryCode("ES")),
            play_mode=PlayMode.HANDICAP,
            tournament_type=TournamentType.MEDAL,
            status=CompetitionStatus.ACTIVE,
            category_limits=[Decimal("12.0")],
            visibility=Visibility.PUBLIC,
            max_players=2,
        )
        async with self.uow:
            await self.uow.competitions.add(self.competicion)
            if con_franjas:
                await self.uow.rounds.add(
                    Round.create_franja(
                        competition_id=self.competicion.id,
                        golf_course_id=GolfCourseId.generate(),
                        round_date=DIA,
                        session_type=SessionType.MORNING,
                        hoja_de_salidas=HojaDeSalidas(time(9, 0), time(10, 0), 10, 4),
                    )
                )
        # El máximo, lleno
        for _ in range(2):
            await self.inscripcion((await self.usuario()).id, EnrollmentStatus.APPROVED)
        return self

    async def usuario(self) -> User:
        user = User.create(
            first_name="Ju",
            last_name="Gador",
            email_str=f"cupo_{uuid4().hex[:8]}@test.com",
            plain_password="SecureP@ssw0rd123",
            gender=Gender.MALE,
        )
        user.update_handicap(12.0)
        async with self.usuarios:
            await self.usuarios.users.save(user)
        return user

    async def inscripcion(self, user_id, estado) -> Enrollment:
        if estado is EnrollmentStatus.APPROVED:
            inscripcion = Enrollment.direct_enroll(
                id=EnrollmentId.generate(), competition_id=self.competicion.id, user_id=user_id
            )
        else:
            inscripcion = Enrollment.request(
                id=EnrollmentId.generate(), competition_id=self.competicion.id, user_id=user_id
            )
        async with self.uow:
            await self.uow.enrollments.add(inscripcion)
        return inscripcion

    async def invitacion(self, invitado: User) -> Invitation:
        invitacion = Invitation.create(
            id=InvitationId.generate(),
            competition_id=self.competicion.id,
            inviter_id=self.creador.id,
            invitee_email=str(invitado.email),
            invitee_user_id=invitado.id,
        )
        async with self.uow:
            await self.uow.invitations.add(invitacion)
        return invitacion

    async def estado(self, invitacion):
        async with self.uow:
            return (await self.uow.invitations.find_by_id(invitacion.id)).status


async def test_c1_el_organizador_inscribe_a_mano_aunque_el_maximo_este_lleno():
    e = await _E().montar(con_franjas=True)
    jugador = await e.usuario()

    respuesta = await DirectEnrollPlayerUseCase(e.uow, e.usuarios.users).execute(
        DirectEnrollPlayerRequestDTO(
            competition_id=e.competicion.id.value, user_id=jugador.id.value
        ),
        e.creador.id,
    )

    assert respuesta.status == "APPROVED"


async def test_c1_y_no_cierra_las_invitaciones_pendientes():
    e = await _E().montar(con_franjas=True)
    pendiente = await e.invitacion(await e.usuario())
    jugador = await e.usuario()

    await DirectEnrollPlayerUseCase(e.uow, e.usuarios.users).execute(
        DirectEnrollPlayerRequestDTO(
            competition_id=e.competicion.id.value, user_id=jugador.id.value
        ),
        e.creador.id,
    )

    assert await e.estado(pendiente) == InvitationStatus.PENDING


async def test_c2_el_organizador_aprueba_una_solicitud():
    e = await _E().montar(con_franjas=True)
    pendiente = await e.invitacion(await e.usuario())
    solicitud = await e.inscripcion((await e.usuario()).id, EnrollmentStatus.REQUESTED)

    respuesta = await HandleEnrollmentUseCase(e.uow, e.usuarios.users).execute(
        HandleEnrollmentRequestDTO(enrollment_id=solicitud.id.value, action="APPROVE"),
        e.creador.id,
    )

    assert respuesta.status == "APPROVED"
    assert await e.estado(pendiente) == InvitationStatus.PENDING


async def test_c3_el_invitado_acepta_y_las_demas_siguen_pendientes():
    e = await _E().montar(con_franjas=True)
    invitado = await e.usuario()
    suya = await e.invitacion(invitado)
    otra = await e.invitacion(await e.usuario())

    await RespondToInvitationUseCase(e.uow, e.usuarios).execute(
        RespondInvitationRequestDTO(
            invitation_id=suya.id.value, user_id=invitado.id.value, action="ACCEPT"
        )
    )

    assert await e.estado(suya) == InvitationStatus.ACCEPTED
    assert await e.estado(otra) == InvitationStatus.PENDING


async def test_c4_el_organizador_invita():
    e = await _E().montar(con_franjas=True)
    invitado = await e.usuario()

    respuesta = await SendInvitationByUserIdUseCase(e.uow, e.usuarios).execute(
        SendInvitationByUserIdRequestDTO(
            competition_id=e.competicion.id.value,
            inviter_id=e.creador.id.value,
            invitee_user_id=invitado.id.value,
        )
    )

    assert respuesta.status == "PENDING"


async def test_c5_sin_franjas_el_maximo_manda_como_siempre():
    e = await _E().montar(con_franjas=False)
    jugador = await e.usuario()

    with pytest.raises(CompetitionFullError):
        await DirectEnrollPlayerUseCase(e.uow, e.usuarios.users).execute(
            DirectEnrollPlayerRequestDTO(
                competition_id=e.competicion.id.value, user_id=jugador.id.value
            ),
            e.creador.id,
        )
