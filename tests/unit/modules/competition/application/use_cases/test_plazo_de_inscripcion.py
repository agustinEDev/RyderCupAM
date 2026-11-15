"""
Pasado el plazo de inscripción nadie entra (15 nov 2026).

| Caso | Acción                                    | Pasado el plazo, abierta antes | Abierta tarde (R1/R2) |
|------|-------------------------------------------|--------------------------------|-----------------------|
| C2   | apuntarse a una pública                   | ENROLLMENT_DEADLINE_PASSED     | entra                 |
| C2   | invitar por id                            | ENROLLMENT_DEADLINE_PASSED     | invita                |
| C2   | invitar por correo                        | ENROLLMENT_DEADLINE_PASSED     | -                     |
| C2   | aceptar una invitación                    | ENROLLMENT_DEADLINE_PASSED     | -                     |
| C2   | rechazarla                                | se rechaza                     | -                     |
| C2   | aprobar una solicitud                     | ENROLLMENT_DEADLINE_PASSED     | -                     |
| C2   | rechazar una solicitud                    | se rechaza                     | -                     |
| C2   | antes del plazo                           | todo como siempre              | -                     |
| C2   | sin plazo en el caso de uso               | como siempre (fuera de la API) | -                     |
| R1   | reabrir pasado el plazo                   | se vuelve a entrar             |                       |
| R2   | invitar a un borrador pasado el plazo     | lo abre, y entra               |                       |
| R2   | crear una competición con el plazo pasado | se entra                       |                       |
| C1   | sin campo, la hora de Madrid              | cierra a las 12:00 de Madrid   |                       |
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
    ReopenEnrollmentsRequestDTO,
)
from src.modules.competition.application.dto.enrollment_dto import (
    HandleEnrollmentRequestDTO,
    RequestEnrollmentRequestDTO,
)
from src.modules.competition.application.dto.invitation_dto import (
    RespondInvitationRequestDTO,
    SendInvitationByEmailRequestDTO,
    SendInvitationByUserIdRequestDTO,
)
from src.modules.competition.application.services.plazo_de_inscripcion import (
    EnrollmentDeadlinePassedError,
    PlazoDeInscripcion,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.handle_enrollment_use_case import (
    HandleEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.reopen_enrollments_use_case import (
    ReopenEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.request_enrollment_use_case import (
    RequestEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.respond_to_invitation_use_case import (
    RespondToInvitationUseCase,
)
from src.modules.competition.application.use_cases.send_invitation_by_email_use_case import (
    SendInvitationByEmailUseCase,
)
from src.modules.competition.application.use_cases.send_invitation_by_user_id_use_case import (
    SendInvitationByUserIdUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as CompetitionInMemoryUoW,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UserInMemoryUoW,
)
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.play_mode import PlayMode
from tests.unit.modules.competition.application.use_cases.helpers import USUARIOS_CON_GENERO

pytestmark = pytest.mark.asyncio

# Se juega pasado mañana: el plazo es mañana a las 12:00 de Madrid
HOY = datetime.now(UTC).date()
TORNEO = HOY + timedelta(days=2)
PLAZO = datetime.combine(TORNEO - timedelta(days=1), datetime.min.time(), tzinfo=UTC)
ANTES = PLAZO - timedelta(days=5)
# Mañana a las 14:00 UTC: pasadas las 12:00 de Madrid en cualquier época del año
DESPUES = PLAZO + timedelta(hours=14)
# Mañana a las 8:00 UTC: antes de las 12:00 de Madrid en cualquier época del año
TODAVIA = PLAZO + timedelta(hours=8)


class _Zonas:
    """Madrid, o la que se diga; y cuenta cuántas veces se le pregunta."""

    def __init__(self, zona: str | None = "Europe/Madrid"):
        self._zona = zona
        self.preguntas = 0

    async def for_competition(self, competition):
        self.preguntas += 1
        return self._zona

    async def for_course(self, golf_course_id):
        return self._zona


def _plazo(ahora: datetime, zona: str | None = "Europe/Madrid") -> PlazoDeInscripcion:
    return PlazoDeInscripcion(_Zonas(zona), reloj=lambda: ahora)


async def _competicion(
    uow: CompetitionInMemoryUoW,
    organizador: UserId,
    abierta: datetime | None = ANTES,
    visibilidad: Visibility = Visibility.PUBLIC,
) -> Competition:
    """Una competición del torneo de pasado mañana, abierta cuando se diga (None: borrador)."""
    competition = Competition.create(
        id=CompetitionId.generate(),
        creator_id=organizador,
        name=CompetitionName(f"Copa {uuid4().hex[:6]}"),
        dates=DateRange(TORNEO, TORNEO + timedelta(days=1)),
        location=Location(main_country="ES"),
        team_1_name="Europa",
        team_2_name="USA",
        play_mode=PlayMode.SCRATCH,
        max_players=24,
        visibility=visibilidad,
        enrollment_opens_days_before=None if abierta is not None else 5,
    )
    if abierta is not None:
        competition.activate(now=abierta)
    async with uow:
        await uow.competitions.add(competition)
    return competition


async def _usuario(user_uow: UserInMemoryUoW, correo: str | None = None) -> User:
    usuario = User.create(
        first_name="Ana",
        last_name="Plazo",
        email_str=correo or f"ana-{uuid4().hex[:6]}@test.com",
        plain_password="SecureP@ssw0rd123",
        gender=Gender.FEMALE,
    )
    async with user_uow:
        await user_uow.users.save(usuario)
    return usuario


async def _invitacion(uow, competition: Competition, invitado: User) -> Invitation:
    invitacion = Invitation.create(
        id=InvitationId.generate(),
        competition_id=competition.id,
        inviter_id=competition.creator_id,
        invitee_email=str(invitado.email),
        invitee_user_id=invitado.id,
    )
    async with uow:
        await uow.invitations.add(invitacion)
    return invitacion


async def _solicitud(uow, competition: Competition, quien: UserId) -> Enrollment:
    solicitud = Enrollment.request(
        id=EnrollmentId.generate(), competition_id=competition.id, user_id=quien
    )
    async with uow:
        await uow.enrollments.add(solicitud)
    return solicitud


class TestApuntarseAUnaPublica:
    async def _apuntarse(self, uow, competition, plazo):
        return await RequestEnrollmentUseCase(uow, USUARIOS_CON_GENERO, plazo=plazo).execute(
            RequestEnrollmentRequestDTO(
                competition_id=competition.id.value, user_id=UserId.generate().value
            )
        )

    async def test_pasado_el_plazo_no_se_entra_aunque_siga_activa(self):
        """
        C2. Given una pública ACTIVE abierta antes del plazo
        When alguien se apunta pasado el plazo
        Then ENROLLMENT_DEADLINE_PASSED, «La inscripción está cerrada.», y no entra
        """
        uow = CompetitionInMemoryUoW()
        competition = await _competicion(uow, UserId.generate())

        with pytest.raises(EnrollmentDeadlinePassedError) as error:
            await self._apuntarse(uow, competition, _plazo(DESPUES))

        assert error.value.error_code == "ENROLLMENT_DEADLINE_PASSED"
        assert str(error.value) == "La inscripción está cerrada."
        async with uow:
            assert await uow.enrollments.count_approved(competition.id) == 0

    async def test_antes_del_plazo_se_entra(self):
        """C2. Given la misma / When se apunta antes del plazo / Then entra."""
        uow = CompetitionInMemoryUoW()
        competition = await _competicion(uow, UserId.generate())

        respuesta = await self._apuntarse(uow, competition, _plazo(TODAVIA))

        assert respuesta.status == EnrollmentStatus.APPROVED.value

    async def test_abierta_tarde_se_entra(self):
        """R2. Given abierta después del plazo / When se apunta / Then entra."""
        uow = CompetitionInMemoryUoW()
        competition = await _competicion(uow, UserId.generate(), abierta=DESPUES)

        respuesta = await self._apuntarse(uow, competition, _plazo(DESPUES + timedelta(hours=1)))

        assert respuesta.status == EnrollmentStatus.APPROVED.value

    async def test_sin_plazo_en_el_caso_de_uso_no_se_mira(self):
        """C2. Given el caso de uso sin plazo (fuera de la API) / Then como siempre."""
        uow = CompetitionInMemoryUoW()
        competition = await _competicion(uow, UserId.generate(), abierta=datetime(2020, 1, 1))

        respuesta = await self._apuntarse(uow, competition, None)

        assert respuesta.status == EnrollmentStatus.APPROVED.value

    async def test_sin_campo_cierra_a_las_doce_de_madrid(self):
        """C1. Given sin campo (zona None) / When pasado el plazo de Madrid / Then cerrada."""
        uow = CompetitionInMemoryUoW()
        competition = await _competicion(uow, UserId.generate())

        with pytest.raises(EnrollmentDeadlinePassedError):
            await self._apuntarse(uow, competition, _plazo(DESPUES, zona=None))

    async def test_la_zona_es_la_del_campo(self):
        """
        C1. Given un campo en Honolulu (UTC-10)
        When son mañana las 14:00 UTC (las 4:00 de allí)
        Then todavía se entra
        """
        uow = CompetitionInMemoryUoW()
        competition = await _competicion(uow, UserId.generate())

        respuesta = await self._apuntarse(uow, competition, _plazo(DESPUES, "Pacific/Honolulu"))

        assert respuesta.status == EnrollmentStatus.APPROVED.value


class TestInvitar:
    async def test_por_id_pasado_el_plazo_no(self):
        """C2. Given ACTIVE abierta antes / When se invita por id pasado el plazo / Then no."""
        uow, user_uow = CompetitionInMemoryUoW(), UserInMemoryUoW()
        organizador = await _usuario(user_uow)
        invitado = await _usuario(user_uow)
        competition = await _competicion(uow, organizador.id, visibilidad=Visibility.PRIVATE)

        with pytest.raises(EnrollmentDeadlinePassedError):
            await SendInvitationByUserIdUseCase(uow, user_uow, plazo=_plazo(DESPUES)).execute(
                SendInvitationByUserIdRequestDTO(
                    competition_id=competition.id.value,
                    inviter_id=organizador.id.value,
                    invitee_user_id=invitado.id.value,
                )
            )

        async with uow:
            assert await uow.invitations.count_by_competition(competition.id) == 0

    async def test_por_id_antes_del_plazo_si(self):
        """C2. Given la misma / When se invita antes del plazo / Then se invita."""
        uow, user_uow = CompetitionInMemoryUoW(), UserInMemoryUoW()
        organizador = await _usuario(user_uow)
        invitado = await _usuario(user_uow)
        competition = await _competicion(uow, organizador.id, visibilidad=Visibility.PRIVATE)

        respuesta = await SendInvitationByUserIdUseCase(
            uow, user_uow, plazo=_plazo(TODAVIA)
        ).execute(
            SendInvitationByUserIdRequestDTO(
                competition_id=competition.id.value,
                inviter_id=organizador.id.value,
                invitee_user_id=invitado.id.value,
            )
        )

        assert respuesta.status == InvitationStatus.PENDING.value

    async def test_a_un_borrador_pasado_el_plazo_lo_abre_tarde_y_se_puede(self):
        """
        R2. Given un borrador (apertura programada) con el plazo ya pasado
        When el organizador invita
        Then lo abre —tarde— y la invitación sale; y luego se puede aceptar
        """
        uow, user_uow = CompetitionInMemoryUoW(), UserInMemoryUoW()
        organizador = await _usuario(user_uow)
        invitado = await _usuario(user_uow)
        competition = await _competicion(uow, organizador.id, abierta=None)
        plazo = PlazoDeInscripcion(_Zonas(), reloj=lambda: datetime.now(UTC))
        # El torneo de pasado mañana: para que su plazo ya haya pasado de verdad
        competition._dates = DateRange(HOY, HOY + timedelta(days=1))

        respuesta = await SendInvitationByUserIdUseCase(uow, user_uow, plazo=plazo).execute(
            SendInvitationByUserIdRequestDTO(
                competition_id=competition.id.value,
                inviter_id=organizador.id.value,
                invitee_user_id=invitado.id.value,
            )
        )

        assert respuesta.status == InvitationStatus.PENDING.value
        async with uow:
            abierta = await uow.competitions.find_by_id(competition.id)
        assert abierta.status is CompetitionStatus.ACTIVE
        assert await plazo.vencido(abierta) is False

    async def test_por_correo_pasado_el_plazo_no(self):
        """C2. Given ACTIVE abierta antes / When se invita por correo pasado el plazo / Then no."""
        uow, user_uow = CompetitionInMemoryUoW(), UserInMemoryUoW()
        organizador = await _usuario(user_uow)
        competition = await _competicion(uow, organizador.id, visibilidad=Visibility.PRIVATE)

        with pytest.raises(EnrollmentDeadlinePassedError):
            await SendInvitationByEmailUseCase(uow, user_uow, plazo=_plazo(DESPUES)).execute(
                SendInvitationByEmailRequestDTO(
                    competition_id=competition.id.value,
                    inviter_id=organizador.id.value,
                    invitee_email="alguien@test.com",
                )
            )

        async with uow:
            assert await uow.invitations.count_by_competition(competition.id) == 0

    async def test_por_correo_antes_del_plazo_si(self):
        """C2. Given la misma / When se invita por correo antes del plazo / Then se invita."""
        uow, user_uow = CompetitionInMemoryUoW(), UserInMemoryUoW()
        organizador = await _usuario(user_uow)
        competition = await _competicion(uow, organizador.id, visibilidad=Visibility.PRIVATE)

        respuesta = await SendInvitationByEmailUseCase(
            uow, user_uow, plazo=_plazo(TODAVIA)
        ).execute(
            SendInvitationByEmailRequestDTO(
                competition_id=competition.id.value,
                inviter_id=organizador.id.value,
                invitee_email="alguien@test.com",
            )
        )

        assert respuesta.status == InvitationStatus.PENDING.value


class TestResponderAUnaInvitacion:
    async def _responder(self, uow, user_uow, invitacion, invitado, accion, plazo):
        return await RespondToInvitationUseCase(uow, user_uow, plazo=plazo).execute(
            RespondInvitationRequestDTO(
                invitation_id=invitacion.id.value, user_id=invitado.id.value, action=accion
            )
        )

    async def test_aceptar_pasado_el_plazo_no(self):
        """C2. Given invitado a una ACTIVE abierta antes / When acepta pasado el plazo / Then no."""
        uow, user_uow = CompetitionInMemoryUoW(), UserInMemoryUoW()
        organizador = await _usuario(user_uow)
        invitado = await _usuario(user_uow)
        competition = await _competicion(uow, organizador.id, visibilidad=Visibility.PRIVATE)
        invitacion = await _invitacion(uow, competition, invitado)

        with pytest.raises(EnrollmentDeadlinePassedError):
            await self._responder(uow, user_uow, invitacion, invitado, "ACCEPT", _plazo(DESPUES))

        async with uow:
            assert await uow.enrollments.count_approved(competition.id) == 0
            sigue = await uow.invitations.find_by_id(invitacion.id)
        assert sigue.status is InvitationStatus.PENDING

    async def test_aceptar_antes_del_plazo_si(self):
        """C2. Given la misma / When acepta antes del plazo / Then entra."""
        uow, user_uow = CompetitionInMemoryUoW(), UserInMemoryUoW()
        organizador = await _usuario(user_uow)
        invitado = await _usuario(user_uow)
        competition = await _competicion(uow, organizador.id, visibilidad=Visibility.PRIVATE)
        invitacion = await _invitacion(uow, competition, invitado)

        respuesta = await self._responder(
            uow, user_uow, invitacion, invitado, "ACCEPT", _plazo(TODAVIA)
        )

        assert respuesta.status == InvitationStatus.ACCEPTED.value

    async def test_rechazar_pasado_el_plazo_si(self):
        """C2. Given la misma / When la rechaza pasado el plazo / Then se rechaza: no entra nadie."""
        uow, user_uow = CompetitionInMemoryUoW(), UserInMemoryUoW()
        organizador = await _usuario(user_uow)
        invitado = await _usuario(user_uow)
        competition = await _competicion(uow, organizador.id, visibilidad=Visibility.PRIVATE)
        invitacion = await _invitacion(uow, competition, invitado)

        respuesta = await self._responder(
            uow, user_uow, invitacion, invitado, "DECLINE", _plazo(DESPUES)
        )

        assert respuesta.status == InvitationStatus.DECLINED.value


class TestLasSolicitudes:
    async def _decidir(self, uow, solicitud, organizador, accion, plazo):
        return await HandleEnrollmentUseCase(uow, USUARIOS_CON_GENERO, plazo=plazo).execute(
            HandleEnrollmentRequestDTO(enrollment_id=solicitud.id.value, action=accion),
            organizador,
        )

    async def test_aprobar_pasado_el_plazo_no(self):
        """C2. Given una solicitud en una ACTIVE abierta antes / When se aprueba tarde / Then no."""
        uow = CompetitionInMemoryUoW()
        organizador = UserId.generate()
        competition = await _competicion(uow, organizador)
        solicitud = await _solicitud(uow, competition, UserId.generate())

        with pytest.raises(EnrollmentDeadlinePassedError):
            await self._decidir(uow, solicitud, organizador, "APPROVE", _plazo(DESPUES))

        async with uow:
            sigue = await uow.enrollments.find_by_id(solicitud.id)
        assert sigue.status is EnrollmentStatus.REQUESTED

    async def test_aprobar_en_una_cerrada_pasado_el_plazo_tampoco(self):
        """C2. Given una Ryder ya cerrada a mano / When se aprueba pasado el plazo / Then no."""
        uow = CompetitionInMemoryUoW()
        organizador = UserId.generate()
        competition = await _competicion(uow, organizador)
        solicitud = await _solicitud(uow, competition, UserId.generate())
        async with uow:
            cerrada = await uow.competitions.find_by_id(competition.id)
            cerrada.close_enrollments()
            await uow.competitions.update(cerrada)

        with pytest.raises(EnrollmentDeadlinePassedError):
            await self._decidir(uow, solicitud, organizador, "APPROVE", _plazo(DESPUES))

    async def test_aprobar_antes_del_plazo_si(self):
        """C2. Given la misma / When se aprueba antes del plazo / Then entra."""
        uow = CompetitionInMemoryUoW()
        organizador = UserId.generate()
        competition = await _competicion(uow, organizador)
        solicitud = await _solicitud(uow, competition, UserId.generate())

        respuesta = await self._decidir(uow, solicitud, organizador, "APPROVE", _plazo(TODAVIA))

        assert respuesta.status == EnrollmentStatus.APPROVED.value

    async def test_rechazar_pasado_el_plazo_si(self):
        """C2. Given la misma / When se rechaza pasado el plazo / Then se rechaza."""
        uow = CompetitionInMemoryUoW()
        organizador = UserId.generate()
        competition = await _competicion(uow, organizador)
        solicitud = await _solicitud(uow, competition, UserId.generate())

        respuesta = await self._decidir(uow, solicitud, organizador, "REJECT", _plazo(DESPUES))

        assert respuesta.status == EnrollmentStatus.REJECTED.value


class TestReabrirTarde:
    async def test_reabierta_pasado_el_plazo_se_vuelve_a_entrar(self):
        """
        R1. Given cerrada a mano, y el plazo pasado
        When el organizador reabre
        Then se vuelve a entrar, y al plazo no le toca cerrarla
        """
        uow = CompetitionInMemoryUoW()
        organizador = UserId.generate()
        competition = await _competicion(uow, organizador)
        async with uow:
            cerrada = await uow.competitions.find_by_id(competition.id)
            cerrada.close_enrollments()
            await uow.competitions.update(cerrada)

        await ReopenEnrollmentsUseCase(uow, reloj=lambda: DESPUES).execute(
            ReopenEnrollmentsRequestDTO(competition_id=competition.id.value), organizador
        )

        plazo = _plazo(DESPUES + timedelta(hours=1))
        async with uow:
            reabierta = await uow.competitions.find_by_id(competition.id)
        assert reabierta.enrollment_opened_at == DESPUES.replace(tzinfo=None)
        assert await plazo.vencido(reabierta) is False
        await RequestEnrollmentUseCase(uow, USUARIOS_CON_GENERO, plazo=plazo).execute(
            RequestEnrollmentRequestDTO(
                competition_id=competition.id.value, user_id=UserId.generate().value
            )
        )


class TestCrearTarde:
    async def test_creada_con_el_plazo_pasado_se_entra(self):
        """R2. Given creada hoy para un torneo de hoy / When alguien se apunta / Then entra."""
        uow = CompetitionInMemoryUoW()
        creada = await CreateCompetitionUseCase(
            uow, LocationBuilder(uow.countries), USUARIOS_CON_GENERO
        ).execute(
            CreateCompetitionRequestDTO(
                name="Copa de hoy",
                start_date=HOY,
                end_date=HOY + timedelta(days=1),
                main_country="ES",
                play_mode="SCRATCH",
                max_players=24,
                visibility="PUBLIC",
            ),
            UserId.generate(),
        )
        plazo = PlazoDeInscripcion(_Zonas(), reloj=lambda: datetime.now(UTC))

        respuesta = await RequestEnrollmentUseCase(uow, USUARIOS_CON_GENERO, plazo=plazo).execute(
            RequestEnrollmentRequestDTO(competition_id=creada.id, user_id=UserId.generate().value)
        )

        assert respuesta.status == EnrollmentStatus.APPROVED.value


class TestElServicio:
    async def test_en_borrador_ni_pregunta_la_zona(self):
        """C2. Given un borrador / When se mira el plazo / Then no se paga la consulta de la zona."""
        uow = CompetitionInMemoryUoW()
        competition = await _competicion(uow, UserId.generate(), abierta=None)
        zonas = _Zonas()

        assert await PlazoDeInscripcion(zonas, reloj=lambda: DESPUES).vencido(competition) is False
        assert zonas.preguntas == 0

    async def test_el_reloj_por_defecto_es_el_de_ahora(self):
        """C2. Given sin reloj / Then el de ahora, en UTC."""
        antes = datetime.now(UTC)

        ahora = PlazoDeInscripcion(_Zonas()).ahora()

        assert ahora.tzinfo is not None
        assert antes <= ahora <= datetime.now(UTC)
