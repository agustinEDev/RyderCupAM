"""
Invitar solo con plazas, retirar una invitación y llenarse (BE #359).

Decidido con Agustín:
- Se invita solo mientras queden plazas: libres = `max_players` menos aprobadas.
- El organizador, quien la envió y el admin pueden retirar una pendiente:
  queda `CANCELLED`, distinto de que el invitado diga que no, y sin avisarle.
- Cuando una aceptación llena la última plaza, las pendientes que quedan se
  quedan sin plaza (`NO_ROOM`), como al cerrar la inscripción (#710).
"""

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.dto.enrollment_dto import (
    DirectEnrollPlayerRequestDTO,
    HandleEnrollmentRequestDTO,
)
from src.modules.competition.application.dto.invitation_dto import (
    RespondInvitationRequestDTO,
    SendInvitationByEmailRequestDTO,
    SendInvitationByUserIdRequestDTO,
)
from src.modules.competition.application.exceptions import (
    InvitationNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.use_cases.cancel_invitation_use_case import (
    CancelInvitationUseCase,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.direct_enroll_player_use_case import (
    DirectEnrollPlayerUseCase,
)
from src.modules.competition.application.use_cases.handle_enrollment_use_case import (
    HandleEnrollmentUseCase,
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
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.exceptions.competition_violations import (
    CompetitionFullViolation,
    InvalidInvitationStatusViolation,
)
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as CompetitionInMemoryUoW,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UserInMemoryUoW,
)
from src.shared.domain.value_objects.gender import Gender
from tests.unit.modules.competition.application.use_cases.helpers import USUARIOS_CON_GENERO

pytestmark = pytest.mark.asyncio


async def _usuario(user_uow, email):
    nombre = email.split("@")[0].capitalize()
    user = User.create(
        first_name=nombre,
        last_name="Prueba",
        email_str=email,
        plain_password="SecureP@ssw0rd123",
        gender=Gender.MALE,
    )
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _competicion(comp_uow, creador, plazas):
    """Abierta, con el organizador ya inscrito: ocupa una plaza."""
    return await CreateCompetitionUseCase(
        comp_uow, LocationBuilder(comp_uow.countries), USUARIOS_CON_GENERO
    ).execute(
        CreateCompetitionRequestDTO(
            name="Ryder del club",
            start_date=date(2026, 12, 1),
            end_date=date(2026, 12, 3),
            main_country="ES",
            play_mode="SCRATCH",
            max_players=plazas,
        ),
        creador.id,
    )


async def _pendiente(comp_uow, competicion_id, quien_invita, invitado):
    invitacion = Invitation.create(
        id=InvitationId.generate(),
        competition_id=CompetitionId(competicion_id),
        inviter_id=quien_invita.id,
        invitee_email=str(invitado.email),
        invitee_user_id=invitado.id,
    )
    async with comp_uow:
        await comp_uow.invitations.add(invitacion)
    return invitacion


async def _estado(comp_uow, invitacion):
    async with comp_uow:
        return (await comp_uow.invitations.find_by_id(invitacion.id)).status


# ==================== La entidad ====================


class TestRetirarEnLaEntidad:
    def _nueva(self):
        return Invitation.create(
            id=InvitationId.generate(),
            competition_id=CompetitionId(uuid4()),
            inviter_id=User.create(
                first_name="A",
                last_name="B",
                email_str="a@b.com",
                plain_password="SecureP@ssw0rd123",
            ).id,
            invitee_email="x@y.com",
        )

    def test_d1_una_pendiente_se_retira(self):
        invitacion = self._nueva()

        invitacion.cancel()

        assert invitacion.status == InvitationStatus.CANCELLED
        assert invitacion.responded_at is not None

    @pytest.mark.parametrize("respuesta", ["accept", "decline", "reject_for_no_room"])
    def test_d2_una_ya_resuelta_no_se_retira(self, respuesta):
        invitacion = self._nueva()
        getattr(invitacion, respuesta)()

        with pytest.raises(InvalidInvitationStatusViolation):
            invitacion.cancel()

    def test_d3_una_retirada_ya_no_se_acepta(self):
        invitacion = self._nueva()
        invitacion.cancel()

        with pytest.raises(InvalidInvitationStatusViolation):
            invitacion.accept()
        assert InvitationStatus.CANCELLED.is_final()


# ==================== Retirar ====================


class TestRetirar:
    @pytest.fixture
    def comp_uow(self):
        return CompetitionInMemoryUoW()

    @pytest.fixture
    def user_uow(self):
        return UserInMemoryUoW()

    async def _montaje(self, comp_uow, user_uow):
        creador = await _usuario(user_uow, "creador@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        invitacion = await _pendiente(comp_uow, comp.id, creador, invitado)
        return creador, invitado, comp, invitacion

    async def test_x1_el_organizador_la_retira(self, comp_uow, user_uow):
        creador, _, _, invitacion = await self._montaje(comp_uow, user_uow)

        await CancelInvitationUseCase(comp_uow).execute(invitacion.id.value, creador.id.value)

        assert await _estado(comp_uow, invitacion) == InvitationStatus.CANCELLED

    async def test_x2_quien_la_envio_la_retira_aunque_no_sea_el_organizador(
        self, comp_uow, user_uow
    ):
        creador = await _usuario(user_uow, "creador@test.com")
        admin = await _usuario(user_uow, "admin@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        invitacion = await _pendiente(comp_uow, comp.id, admin, invitado)

        await CancelInvitationUseCase(comp_uow).execute(invitacion.id.value, admin.id.value)

        assert await _estado(comp_uow, invitacion) == InvitationStatus.CANCELLED

    async def test_x2b_el_organizador_retira_una_que_envio_otro(self, comp_uow, user_uow):
        creador = await _usuario(user_uow, "creador@test.com")
        admin = await _usuario(user_uow, "admin@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        invitacion = await _pendiente(comp_uow, comp.id, admin, invitado)

        await CancelInvitationUseCase(comp_uow).execute(invitacion.id.value, creador.id.value)

        assert await _estado(comp_uow, invitacion) == InvitationStatus.CANCELLED

    async def test_x3_el_admin_la_retira(self, comp_uow, user_uow):
        _, _, _, invitacion = await self._montaje(comp_uow, user_uow)

        await CancelInvitationUseCase(comp_uow).execute(invitacion.id.value, uuid4(), is_admin=True)

        assert await _estado(comp_uow, invitacion) == InvitationStatus.CANCELLED

    @pytest.mark.parametrize("quien", ["otro", "invitado"])
    async def test_x4_nadie_mas_puede(self, comp_uow, user_uow, quien):
        _, invitado, _, invitacion = await self._montaje(comp_uow, user_uow)
        usuario = invitado.id.value if quien == "invitado" else uuid4()

        with pytest.raises(NotCompetitionCreatorError):
            await CancelInvitationUseCase(comp_uow).execute(invitacion.id.value, usuario)

        assert await _estado(comp_uow, invitacion) == InvitationStatus.PENDING

    async def test_x5_una_que_no_existe(self, comp_uow):
        with pytest.raises(InvitationNotFoundError):
            await CancelInvitationUseCase(comp_uow).execute(uuid4(), uuid4(), is_admin=True)

    async def test_x7_una_caducada_sin_marcar_queda_caducada_no_retirada(self, comp_uow, user_uow):
        creador = await _usuario(user_uow, "creador@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        caducada = Invitation.reconstruct(
            id=InvitationId.generate(),
            competition_id=CompetitionId(comp.id),
            inviter_id=creador.id,
            invitee_email=str(invitado.email),
            invitee_user_id=invitado.id,
            status=InvitationStatus.PENDING,
            expires_at=datetime.now() - timedelta(days=1),
        )
        async with comp_uow:
            await comp_uow.invitations.add(caducada)

        with pytest.raises(InvalidInvitationStatusViolation, match="EXPIRED"):
            await CancelInvitationUseCase(comp_uow).execute(caducada.id.value, creador.id.value)

        assert await _estado(comp_uow, caducada) == InvitationStatus.EXPIRED

    async def test_x6_una_ya_respondida_no_se_retira(self, comp_uow, user_uow):
        creador, invitado, _, invitacion = await self._montaje(comp_uow, user_uow)
        await RespondToInvitationUseCase(comp_uow, user_uow).execute(
            RespondInvitationRequestDTO(
                invitation_id=invitacion.id.value, user_id=invitado.id.value, action="DECLINE"
            )
        )

        with pytest.raises(InvalidInvitationStatusViolation):
            await CancelInvitationUseCase(comp_uow).execute(invitacion.id.value, creador.id.value)

        assert await _estado(comp_uow, invitacion) == InvitationStatus.DECLINED


# ==================== Invitar solo con plazas ====================


class TestInvitarConPlazas:
    @pytest.fixture
    def comp_uow(self):
        return CompetitionInMemoryUoW()

    @pytest.fixture
    def user_uow(self):
        return UserInMemoryUoW()

    async def test_s1_por_id_sin_plazas_no_se_invita(self, comp_uow, user_uow):
        creador = await _usuario(user_uow, "creador@test.com")
        dentro = await _usuario(user_uow, "dentro@test.com")
        fuera = await _usuario(user_uow, "fuera@test.com")
        comp = await _competicion(comp_uow, creador, plazas=2)
        invitacion = await _pendiente(comp_uow, comp.id, creador, dentro)
        await RespondToInvitationUseCase(comp_uow, user_uow).execute(
            RespondInvitationRequestDTO(
                invitation_id=invitacion.id.value, user_id=dentro.id.value, action="ACCEPT"
            )
        )

        with pytest.raises(CompetitionFullViolation):
            await SendInvitationByUserIdUseCase(comp_uow, user_uow).execute(
                SendInvitationByUserIdRequestDTO(
                    competition_id=comp.id,
                    inviter_id=creador.id.value,
                    invitee_user_id=fuera.id.value,
                )
            )

    async def test_s2_por_correo_sin_plazas_no_se_invita(self, comp_uow, user_uow):
        creador = await _usuario(user_uow, "creador@test.com")
        dentro = await _usuario(user_uow, "dentro@test.com")
        comp = await _competicion(comp_uow, creador, plazas=2)
        invitacion = await _pendiente(comp_uow, comp.id, creador, dentro)
        await RespondToInvitationUseCase(comp_uow, user_uow).execute(
            RespondInvitationRequestDTO(
                invitation_id=invitacion.id.value, user_id=dentro.id.value, action="ACCEPT"
            )
        )

        with pytest.raises(CompetitionFullViolation):
            await SendInvitationByEmailUseCase(comp_uow, user_uow).execute(
                SendInvitationByEmailRequestDTO(
                    competition_id=comp.id,
                    inviter_id=creador.id.value,
                    invitee_email="nuevo@test.com",
                )
            )

    async def test_s3_las_pendientes_no_ocupan_plaza(self, comp_uow, user_uow):
        creador = await _usuario(user_uow, "creador@test.com")
        uno = await _usuario(user_uow, "uno@test.com")
        dos = await _usuario(user_uow, "dos@test.com")
        comp = await _competicion(comp_uow, creador, plazas=2)
        await _pendiente(comp_uow, comp.id, creador, uno)

        respuesta = await SendInvitationByUserIdUseCase(comp_uow, user_uow).execute(
            SendInvitationByUserIdRequestDTO(
                competition_id=comp.id, inviter_id=creador.id.value, invitee_user_id=dos.id.value
            )
        )

        assert respuesta.status == "PENDING"


# ==================== Llenarse ====================


class TestAlLlenarse:
    @pytest.fixture
    def comp_uow(self):
        return CompetitionInMemoryUoW()

    @pytest.fixture
    def user_uow(self):
        return UserInMemoryUoW()

    async def _acepta(self, comp_uow, user_uow, invitacion, invitado):
        return await RespondToInvitationUseCase(comp_uow, user_uow).execute(
            RespondInvitationRequestDTO(
                invitation_id=invitacion.id.value, user_id=invitado.id.value, action="ACCEPT"
            )
        )

    async def test_a1_la_que_llena_la_ultima_plaza_deja_sin_plaza_a_las_demas(
        self, comp_uow, user_uow
    ):
        creador = await _usuario(user_uow, "creador@test.com")
        primero = await _usuario(user_uow, "primero@test.com")
        tarde = await _usuario(user_uow, "tarde@test.com")
        comp = await _competicion(comp_uow, creador, plazas=2)
        la_primera = await _pendiente(comp_uow, comp.id, creador, primero)
        la_tardia = await _pendiente(comp_uow, comp.id, creador, tarde)

        respuesta = await self._acepta(comp_uow, user_uow, la_primera, primero)

        assert respuesta.status == "ACCEPTED"
        assert await _estado(comp_uow, la_tardia) == InvitationStatus.NO_ROOM

    async def test_a2_si_quedan_plazas_las_demas_siguen_pendientes(self, comp_uow, user_uow):
        creador = await _usuario(user_uow, "creador@test.com")
        primero = await _usuario(user_uow, "primero@test.com")
        otro = await _usuario(user_uow, "otro@test.com")
        comp = await _competicion(comp_uow, creador, plazas=3)
        la_primera = await _pendiente(comp_uow, comp.id, creador, primero)
        la_otra = await _pendiente(comp_uow, comp.id, creador, otro)

        await self._acepta(comp_uow, user_uow, la_primera, primero)

        assert await _estado(comp_uow, la_otra) == InvitationStatus.PENDING

    # Revisión: aprobar una solicitud también puede llenar la última plaza. Las
    # pendientes no se quedaban sin plaza, y el invitado se enteraba al aceptar
    async def _solicitud(self, comp_uow, competicion_id, jugador):
        solicitud = Enrollment.request(
            EnrollmentId.generate(), CompetitionId(competicion_id), jugador.id
        )
        async with comp_uow:
            await comp_uow.enrollments.add(solicitud)
        return solicitud

    async def _aprueba(self, comp_uow, user_uow, solicitud, creador):
        return await HandleEnrollmentUseCase(comp_uow, user_uow.users).execute(
            HandleEnrollmentRequestDTO(enrollment_id=solicitud.id.value, action="APPROVE"),
            creador.id,
        )

    async def test_a3_aprobar_la_que_llena_deja_sin_plaza_a_las_pendientes(
        self, comp_uow, user_uow
    ):
        creador = await _usuario(user_uow, "creador@test.com")
        pide = await _usuario(user_uow, "pide@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=2)
        solicitud = await self._solicitud(comp_uow, comp.id, pide)
        invitacion = await _pendiente(comp_uow, comp.id, creador, invitado)

        await self._aprueba(comp_uow, user_uow, solicitud, creador)

        assert await _estado(comp_uow, invitacion) == InvitationStatus.NO_ROOM

    async def test_a4_aprobar_sin_llenar_las_deja_pendientes(self, comp_uow, user_uow):
        creador = await _usuario(user_uow, "creador@test.com")
        pide = await _usuario(user_uow, "pide@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=3)
        solicitud = await self._solicitud(comp_uow, comp.id, pide)
        invitacion = await _pendiente(comp_uow, comp.id, creador, invitado)

        await self._aprueba(comp_uow, user_uow, solicitud, creador)

        assert await _estado(comp_uow, invitacion) == InvitationStatus.PENDING

    async def test_a5_inscribir_directamente_la_que_llena_deja_sin_plaza_a_las_pendientes(
        self, comp_uow, user_uow
    ):
        creador = await _usuario(user_uow, "creador@test.com")
        directo = await _usuario(user_uow, "directo@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=2)
        invitacion = await _pendiente(comp_uow, comp.id, creador, invitado)

        await DirectEnrollPlayerUseCase(comp_uow, user_uow.users).execute(
            DirectEnrollPlayerRequestDTO(competition_id=comp.id, user_id=directo.id.value),
            creador.id,
        )

        assert await _estado(comp_uow, invitacion) == InvitationStatus.NO_ROOM
