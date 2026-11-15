"""
Volver a entrar con una inscripción vieja (release social 2, tabla del 27 oct 2026).

Una inscripción rechazada, cancelada o retirada se quedaba en la tabla, y la
restricción única (competición, usuario) no mira el estado: quien la tenía no
podía volver a entrar por ninguna vía. Ahora se reutiliza esa misma fila.

| #  | Caso                                                    | Resultado                       |
|----|---------------------------------------------------------|---------------------------------|
| V1 | Acepta una invitación con una retirada/rechazada vieja  | Entra: la misma fila, APPROVED  |
| V2 | Pide plaza en una pública con una cancelada vieja       | APPROVED (28 oct), la misma fila|
| V3 | El organizador le inscribe con una rechazada vieja      | APPROVED, con su hándicap y barra |
| V4 | Con una APPROVED o pendiente                            | Igual que hoy: ya inscrito      |
| -  | Lo de la vez anterior (equipo, hándicap fijado)         | No se arrastra                  |
"""

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.enrollment_dto import (
    DirectEnrollPlayerRequestDTO,
    RequestEnrollmentRequestDTO,
)
from src.modules.competition.application.dto.invitation_dto import RespondInvitationRequestDTO
from src.modules.competition.application.use_cases.direct_enroll_player_use_case import (
    AlreadyEnrolledError as YaInscritoAMano,
    DirectEnrollPlayerUseCase,
)
from src.modules.competition.application.use_cases.request_enrollment_use_case import (
    AlreadyEnrolledError as YaInscritoAlPedir,
    RequestEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.respond_to_invitation_use_case import (
    RespondToInvitationUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment, EnrollmentStateError
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.exceptions.competition_violations import (
    InvalidInvitationStatusViolation,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UsuariosEnMemoria,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.play_mode import PlayMode

pytestmark = pytest.mark.asyncio

CERRADAS = [EnrollmentStatus.REJECTED, EnrollmentStatus.CANCELLED, EnrollmentStatus.WITHDRAWN]


class _Usuarios:
    async def find_by_id(self, user_id):
        return SimpleNamespace(id=user_id, gender=Gender.MALE, email=None)


def _vieja(competicion_id, user_id, estado) -> Enrollment:
    """Como queda tras rechazarla, cancelarla o retirarse: con su equipo y su hándicap fijado."""
    return Enrollment(
        id=EnrollmentId.generate(),
        competition_id=competicion_id,
        user_id=user_id,
        status=estado,
        team_id="A",
        custom_handicap=Decimal("12.0"),
        tee_color=TeeColor.WHITE,
        fixed_handicap=Decimal("11.0"),
        fixed_category=2,
    )


# ==================== El dominio ====================


@pytest.mark.parametrize("estado", CERRADAS)
@pytest.mark.parametrize(("aprobada", "queda"), [(True, "APPROVED"), (False, "REQUESTED")])
async def test_una_cerrada_vuelve_a_entrar_limpia(estado, aprobada, queda):
    vieja = _vieja(CompetitionId.generate(), UserId(uuid4()), estado)

    vieja.volver_a_entrar(aprobada=aprobada, tee_color=TeeColor.YELLOW, custom_handicap=None)

    assert vieja.status.value == queda
    assert vieja.team_id is None
    assert vieja.custom_handicap is None
    assert vieja.tee_color == TeeColor.YELLOW
    assert vieja.fixed_handicap is None
    assert vieja.fixed_category is None


async def test_vuelve_a_la_cola_con_la_fecha_de_hoy_y_conserva_su_nombre_elegido():
    """
    Decidido el 27 oct: las solicitudes se ordenan por fecha de inscripción, y
    quien vuelve entra como nuevo. El nombre que eligió mostrar es suyo: se queda.
    """
    vieja = _vieja(CompetitionId.generate(), UserId(uuid4()), EnrollmentStatus.REJECTED)
    vieja._created_at = vieja.created_at - timedelta(days=60)
    vieja._use_real_name = False
    antes = vieja.created_at

    vieja.volver_a_entrar(aprobada=False)

    assert vieja.created_at > antes + timedelta(days=59)
    assert vieja.use_real_name is False


async def test_con_su_handicap_nuevo_validado():
    vieja = _vieja(CompetitionId.generate(), UserId(uuid4()), EnrollmentStatus.WITHDRAWN)

    vieja.volver_a_entrar(aprobada=True, custom_handicap=Decimal("8.5"))
    assert vieja.custom_handicap == Decimal("8.5")

    otra = _vieja(CompetitionId.generate(), UserId(uuid4()), EnrollmentStatus.WITHDRAWN)
    with pytest.raises(ValueError):
        otra.volver_a_entrar(aprobada=True, custom_handicap=Decimal("99"))


@pytest.mark.parametrize(
    "estado", [EnrollmentStatus.APPROVED, EnrollmentStatus.REQUESTED, EnrollmentStatus.INVITED]
)
async def test_una_viva_no_vuelve_a_entrar(estado):
    viva = _vieja(CompetitionId.generate(), UserId(uuid4()), estado)

    with pytest.raises(EnrollmentStateError):
        viva.volver_a_entrar(aprobada=True)


# ==================== Los tres caminos ====================


async def _abierta(uow, organizador: UserId, *, publica: bool = False) -> Competition:
    empieza = date.today() + timedelta(days=5)
    competicion = Competition(
        id=CompetitionId.generate(),
        creator_id=organizador,
        name=CompetitionName("Ryder del club"),
        dates=DateRange(empieza, empieza + timedelta(days=1)),
        location=Location(CountryCode("ES")),
        team_1_name="Europa",
        team_2_name="América",
        play_mode=PlayMode.SCRATCH,
        max_players=12,
        status=CompetitionStatus.ACTIVE,
        visibility=Visibility.PUBLIC if publica else Visibility.PRIVATE,
    )
    async with uow:
        await uow.competitions.add(competicion)
    return competicion


async def _con(uow, inscripcion: Enrollment) -> None:
    async with uow:
        await uow.enrollments.add(inscripcion)


async def _suya(uow, competicion, user_id) -> Enrollment:
    async with uow:
        return await uow.enrollments.find_by_user_and_competition(user_id, competicion.id)


async def _invitado(usuarios) -> User:
    usuario = User.create(
        first_name="Pedro",
        last_name="Gil",
        email_str=f"p{uuid4().hex[:6]}@example.com",
        plain_password="SecureP@ssw0rd123",
        gender=Gender.MALE,
    )
    async with usuarios:
        await usuarios.users.save(usuario)
    return usuario


async def _acepta(uow, usuarios, competicion, organizador, invitado):
    invitacion = Invitation.create(
        id=InvitationId.generate(),
        competition_id=competicion.id,
        inviter_id=organizador,
        invitee_email=str(invitado.email),
        invitee_user_id=invitado.id,
    )
    async with uow:
        await uow.invitations.add(invitacion)
    return await RespondToInvitationUseCase(uow, usuarios).execute(
        RespondInvitationRequestDTO(
            invitation_id=invitacion.id.value, user_id=invitado.id.value, action="ACCEPT"
        )
    )


@pytest.mark.parametrize("estado", CERRADAS)
async def test_v1_acepta_una_invitacion_con_una_vieja_y_entra(estado):
    uow, usuarios = InMemoryUnitOfWork(), UsuariosEnMemoria()
    organizador = UserId(uuid4())
    competicion = await _abierta(uow, organizador)
    invitado = await _invitado(usuarios)
    vieja = _vieja(competicion.id, invitado.id, estado)
    await _con(uow, vieja)

    respuesta = await _acepta(uow, usuarios, competicion, organizador, invitado)

    assert respuesta.status == "ACCEPTED"
    suya = await _suya(uow, competicion, invitado.id)
    assert suya.id == vieja.id
    assert suya.status == EnrollmentStatus.APPROVED
    assert suya.team_id is None
    assert respuesta.enrollment_id == vieja.id.value


async def test_acepta_con_su_solicitud_pendiente_y_queda_aprobada():
    """Decidido el 27 oct: queria entrar y le invitan; aceptar aprueba su solicitud."""
    uow, usuarios = InMemoryUnitOfWork(), UsuariosEnMemoria()
    organizador = UserId(uuid4())
    competicion = await _abierta(uow, organizador)
    invitado = await _invitado(usuarios)
    solicitud = Enrollment.request(EnrollmentId.generate(), competicion.id, invitado.id)
    await _con(uow, solicitud)

    respuesta = await _acepta(uow, usuarios, competicion, organizador, invitado)

    assert respuesta.status == "ACCEPTED"
    assert respuesta.enrollment_id == solicitud.id.value
    assert (await _suya(uow, competicion, invitado.id)).status == EnrollmentStatus.APPROVED


@pytest.mark.parametrize("estado", [EnrollmentStatus.APPROVED, EnrollmentStatus.INVITED])
async def test_v4_acepta_con_una_viva_y_sigue_sin_poder(estado):
    uow, usuarios = InMemoryUnitOfWork(), UsuariosEnMemoria()
    organizador = UserId(uuid4())
    competicion = await _abierta(uow, organizador)
    invitado = await _invitado(usuarios)
    await _con(uow, _vieja(competicion.id, invitado.id, estado))

    with pytest.raises(InvalidInvitationStatusViolation):
        await _acepta(uow, usuarios, competicion, organizador, invitado)


@pytest.mark.parametrize("estado", CERRADAS)
async def test_v2_pide_plaza_con_una_vieja_y_sale(estado):
    uow = InMemoryUnitOfWork()
    competicion = await _abierta(uow, UserId(uuid4()), publica=True)
    jugador = UserId(uuid4())
    vieja = _vieja(competicion.id, jugador, estado)
    await _con(uow, vieja)

    respuesta = await RequestEnrollmentUseCase(uow, _Usuarios()).execute(
        RequestEnrollmentRequestDTO(
            competition_id=competicion.id.value, user_id=jugador.value, tee_color="YELLOW"
        )
    )

    assert respuesta.status == "APPROVED"
    assert respuesta.id == vieja.id.value
    suya = await _suya(uow, competicion, jugador)
    assert suya.status == EnrollmentStatus.APPROVED
    assert suya.tee_color == TeeColor.YELLOW


# Una solicitud pendiente de antes ya no bloquea: entra (code-review, 28 oct 2026)
@pytest.mark.parametrize("estado", [EnrollmentStatus.APPROVED])
async def test_v4_pide_plaza_con_una_viva_y_ya_esta(estado):
    uow = InMemoryUnitOfWork()
    competicion = await _abierta(uow, UserId(uuid4()), publica=True)
    jugador = UserId(uuid4())
    await _con(uow, _vieja(competicion.id, jugador, estado))

    with pytest.raises(YaInscritoAlPedir):
        await RequestEnrollmentUseCase(uow, _Usuarios()).execute(
            RequestEnrollmentRequestDTO(competition_id=competicion.id.value, user_id=jugador.value)
        )


@pytest.mark.parametrize("estado", CERRADAS)
async def test_v3_el_organizador_le_inscribe_con_una_vieja(estado):
    uow = InMemoryUnitOfWork()
    organizador = UserId(uuid4())
    competicion = await _abierta(uow, organizador)
    jugador = UserId(uuid4())
    vieja = _vieja(competicion.id, jugador, estado)
    await _con(uow, vieja)

    respuesta = await DirectEnrollPlayerUseCase(uow, _Usuarios()).execute(
        DirectEnrollPlayerRequestDTO(
            competition_id=competicion.id.value,
            user_id=jugador.value,
            custom_handicap=Decimal("7.0"),
            tee_color="YELLOW",
        ),
        organizador,
    )

    assert respuesta.status == "APPROVED"
    suya = await _suya(uow, competicion, jugador)
    assert suya.id == vieja.id
    assert suya.status == EnrollmentStatus.APPROVED
    assert suya.custom_handicap == Decimal("7.0")
    assert suya.tee_color == TeeColor.YELLOW


@pytest.mark.parametrize("estado", [EnrollmentStatus.APPROVED, EnrollmentStatus.INVITED])
async def test_v4_a_mano_con_una_viva_y_ya_esta(estado):
    uow = InMemoryUnitOfWork()
    organizador = UserId(uuid4())
    competicion = await _abierta(uow, organizador)
    jugador = UserId(uuid4())
    await _con(uow, _vieja(competicion.id, jugador, estado))

    with pytest.raises(YaInscritoAMano):
        await DirectEnrollPlayerUseCase(uow, _Usuarios()).execute(
            DirectEnrollPlayerRequestDTO(
                competition_id=competicion.id.value, user_id=jugador.value
            ),
            organizador,
        )
