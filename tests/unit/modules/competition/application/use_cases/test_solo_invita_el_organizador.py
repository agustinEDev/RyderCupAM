"""
El organizador solo invita (auditoría de la fase 6, B-02; decidido por Agustín el
15 nov 2026).

Hasta ahora el organizador podía inscribir a cualquiera sin su consentimiento, y
devolver a la competición a quien se había retirado. Desde hoy, el organizador
invita; inscribirse directamente es cosa del jugador en una pública abierta.

| #  | Caso                                                    | Debe                                          |
|----|---------------------------------------------------------|-----------------------------------------------|
| O1 | La inscripción directa del organizador                  | No existe: ni ruta, ni caso de uso, ni proveedor |
| O2 | Invitar con la inscripción CERRADA (Ryder)              | Se puede: PENDING, y sigue CERRADA            |
| O2 | Invitar EN JUEGO, terminada o cancelada                 | No                                            |
| O3 | Aceptar con la inscripción CERRADA, con sitio           | Entra (APPROVED) e invitación ACCEPTED        |
| O3 | Aceptar CERRADA sin sitio                               | «Sin plaza», como hoy (INVITATION_NO_ROOM)    |
| O3 | Una pendiente con la competición ya en juego            | Sin plaza (NO_ROOM): no entra                 |
| O4 | Cerrar la inscripción a mano                            | Las pendientes siguen PENDING, sin aviso      |
| O5 | Empezar: a mano, primer golpe de partida o de partido,  | Las pendientes, NO_ROOM (las caducadas,       |
|    | o el organizador corrigiendo un hoyo                    | EXPIRED) y se retira su aviso de invitado     |
| O6 | Un jugador que se retiró                                | El organizador no le devuelve: ni aprobando   |
|    |                                                         | su inscripción ni invitándole sin que acepte  |
| P1 | Stableford/Medal CERRADO: invitar                       | No (SIN_PLAZAS, como hasta ahora)             |
| P1 | Stableford/Medal CERRADO: aceptar una pendiente         | No: sigue PENDING; el organizador la reabre   |
| P2 | Ryder con equipos formados, sin partidos: aceptar       | Entra y los equipos se reinician              |
| P2 | Ryder con equipos formados y partidos: aceptar          | TEAMS_FORMED; la invitación sigue PENDING     |
| P3 | Nombrar capitanes (también cierra la inscripción)       | Las pendientes siguen PENDING                 |
| P3 | Aceptar con la sala de draft abierta                    | DRAFT_IN_PROGRESS; la invitación sigue PENDING |

La inscripción del propio jugador en una pública (RequestEnrollmentUseCase, 28 oct)
no cambia. Quien estaba en espera y sale al cerrar (A4) tampoco: es otra cosa.
"""

import importlib.util
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

import src.config.dependencies as dependencias
from src.modules.competition.application.dto.competition_dto import (
    CloseEnrollmentsRequestDTO,
    CreateCompetitionRequestDTO,
    NameCaptainsRequestDTO,
    StartCompetitionRequestDTO,
    StrokePlaySettingsDTO,
)
from src.modules.competition.application.dto.enrollment_dto import (
    HandleEnrollmentRequestDTO,
    WithdrawEnrollmentRequestDTO,
)
from src.modules.competition.application.dto.invitation_dto import (
    RespondInvitationRequestDTO,
    SendInvitationByEmailRequestDTO,
    SendInvitationByUserIdRequestDTO,
)
from src.modules.competition.application.dto.partidas_dto import CorrectHoleBodyDTO
from src.modules.competition.application.dto.scoring_dto import SubmitHoleScoreBodyDTO
from src.modules.competition.application.services.baja_de_la_competicion import (
    DraftInProgressError,
)
from src.modules.competition.application.services.equipos_formados import TeamsFormedError
from src.modules.competition.application.services.team_assignment_writer import (
    TeamAssignmentWriter,
)
from src.modules.competition.application.use_cases.anotar_hoyo_de_partida_use_case import (
    AnotarHoyoDePartidaUseCase,
)
from src.modules.competition.application.use_cases.close_enrollments_use_case import (
    CloseEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.handle_enrollment_use_case import (
    HandleEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.name_captains_use_case import (
    NameCaptainsUseCase,
)
from src.modules.competition.application.use_cases.organizador_de_partidas_use_case import (
    CorregirHoyoDePartidaUseCase,
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
from src.modules.competition.application.use_cases.start_competition_use_case import (
    StartCompetitionUseCase,
)
from src.modules.competition.application.use_cases.submit_hole_score_use_case import (
    SubmitHoleScoreUseCase,
)
from src.modules.competition.application.use_cases.withdraw_enrollment_use_case import (
    WithdrawEnrollmentUseCase,
)
from src.modules.competition.domain.entities.draft import Draft
from src.modules.competition.domain.entities.enrollment import EnrollmentStateError
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.exceptions.competition_violations import (
    InvitationCompetitionStatusViolation,
    InvitationNoRoomViolation,
)
from src.modules.competition.domain.services.competition_policy import CompetitionPolicy
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.draft_id import DraftId
from src.modules.competition.domain.value_objects.draft_status import DraftStatus
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.infrastructure.api.v1.invitation_routes import (
    RespondInvitationBody,
    respond_to_invitation,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as CompetitionInMemoryUoW,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UserInMemoryUoW,
)
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat
from tests.unit.config.test_terms_guard import _routes, app
from tests.unit.modules.competition.application.use_cases.helpers import (
    USUARIOS_CON_GENERO,
    create_approved_enrollment,
    set_competition_status,
)
from tests.unit.modules.competition.application.use_cases.test_anotar_hoyo_de_partida_use_case import (
    _partida,
)
from tests.unit.modules.competition.application.use_cases.test_avisos_de_actividad import (
    _Registro,
    _UsuariosDeLaVista,
)
from tests.unit.modules.competition.application.use_cases.test_deshacer_equipos import (
    _montar,
)
from tests.unit.modules.competition.application.use_cases.test_equipos_formados_congelados import (
    _con_partidos,
)
from tests.unit.modules.competition.application.use_cases.test_invitation_capacity_and_withdraw import (
    _competicion,
    _estado,
    _pendiente,
    _usuario,
)
from tests.unit.modules.competition.application.use_cases.test_submit_hole_score_auto_open import (
    DESPUES,
    _body,
    _monta,
    _ReposDeCampos,
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


def _responde(comp_uow, user_uow, invitacion, quien, actividad=None):
    return RespondToInvitationUseCase(comp_uow, user_uow, actividad=actividad).execute(
        RespondInvitationRequestDTO(
            invitation_id=invitacion.id.value, user_id=quien.id.value, action="ACCEPT"
        )
    )


def _invita(comp_uow, user_uow, comp_id, creador, invitado):
    return SendInvitationByUserIdUseCase(comp_uow, user_uow).execute(
        SendInvitationByUserIdRequestDTO(
            competition_id=comp_id, inviter_id=creador.id.value, invitee_user_id=invitado.id.value
        )
    )


async def _inscripcion(comp_uow, comp_id, user_id):
    async with comp_uow:
        return await comp_uow.enrollments.find_by_user_and_competition(
            user_id, CompetitionId(comp_id)
        )


async def _estado_de_la_competicion(comp_uow, comp_id) -> CompetitionStatus:
    async with comp_uow:
        return (await comp_uow.competitions.find_by_id(CompetitionId(comp_id))).status


# ==================== O1 ====================


class TestO1SinInscripcionDirectaDelOrganizador:
    def test_no_hay_ruta(self):
        """Given la API / When se buscan sus rutas / Then ninguna es la inscripción directa."""
        rutas = {path for path, _ in _routes(app.routes)}

        assert not any(p.endswith("/enrollments/direct") for p in rutas)

    def test_no_hay_caso_de_uso(self):
        modulo = "src.modules.competition.application.use_cases.direct_enroll_player_use_case"

        assert importlib.util.find_spec(modulo) is None

    def test_no_hay_proveedor(self):
        assert not hasattr(dependencias, "get_direct_enroll_player_use_case")

    def test_solo_el_jugador_crea_su_inscripcion_por_la_api(self):
        """Then las únicas rutas que crean una inscripción son las del propio jugador:
        apuntarse él y responder a su invitación (y aprobar, que no crea ninguna)."""
        crean = {
            path
            for path, ruta in _routes(app.routes)
            if "POST" in ruta.methods and path.endswith("/enrollments")
        }

        assert crean == {"/api/v1/competitions/{competition_id}/enrollments"}


# ==================== O2 / P1: invitar ====================


class TestO2InvitarConLaInscripcionCerrada:
    def test_la_politica_deja_invitar_cerrada_en_una_ryder(self):
        CompetitionPolicy.can_send_invitation(CompetitionStatus.CLOSED, stroke_play=False)

    @pytest.mark.parametrize(
        "estado",
        [CompetitionStatus.IN_PROGRESS, CompetitionStatus.COMPLETED, CompetitionStatus.CANCELLED],
    )
    def test_en_juego_o_despues_no(self, estado):
        with pytest.raises(InvitationCompetitionStatusViolation):
            CompetitionPolicy.can_send_invitation(estado, stroke_play=False)

    def test_p1_un_stroke_play_cerrado_no(self):
        with pytest.raises(InvitationCompetitionStatusViolation, match="plazas"):
            CompetitionPolicy.can_send_invitation(CompetitionStatus.CLOSED, stroke_play=True)

    def test_p1_un_stroke_play_abierto_si(self):
        CompetitionPolicy.can_send_invitation(CompetitionStatus.ACTIVE, stroke_play=True)

    async def test_por_id_queda_pendiente_y_la_competicion_sigue_cerrada(self, comp_uow, user_uow):
        """Given una Ryder cerrada / When el organizador invita / Then PENDING, y sigue CLOSED."""
        creador = await _usuario(user_uow, "creador@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        await set_competition_status(comp_uow, comp.id, "CLOSED")

        respuesta = await _invita(comp_uow, user_uow, comp.id, creador, invitado)

        assert respuesta.status == "PENDING"
        assert await _estado_de_la_competicion(comp_uow, comp.id) == CompetitionStatus.CLOSED

    async def test_por_correo_tambien(self, comp_uow, user_uow):
        creador = await _usuario(user_uow, "creador@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        await set_competition_status(comp_uow, comp.id, "CLOSED")

        respuesta = await SendInvitationByEmailUseCase(comp_uow, user_uow).execute(
            SendInvitationByEmailRequestDTO(
                competition_id=comp.id, inviter_id=creador.id.value, invitee_email="x@test.com"
            )
        )

        assert respuesta.status == "PENDING"

    async def test_en_juego_no_se_invita(self, comp_uow, user_uow):
        creador = await _usuario(user_uow, "creador@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        await set_competition_status(comp_uow, comp.id, "IN_PROGRESS")

        with pytest.raises(InvitationCompetitionStatusViolation):
            await _invita(comp_uow, user_uow, comp.id, creador, invitado)

    async def test_p1_en_un_stableford_cerrado_no_se_invita(self, comp_uow, user_uow):
        creador = await _usuario(user_uow, "creador@test.com")
        invitado = await _con_handicap(user_uow, "invitado@test.com")
        comp = await _stableford(comp_uow, creador)
        await set_competition_status(comp_uow, comp.id, "CLOSED")

        with pytest.raises(InvitationCompetitionStatusViolation):
            await _invita(comp_uow, user_uow, comp.id, creador, invitado)

    async def test_p1_en_un_stableford_cerrado_tampoco_por_correo(self, comp_uow, user_uow):
        creador = await _usuario(user_uow, "creador@test.com")
        comp = await _stableford(comp_uow, creador)
        await set_competition_status(comp_uow, comp.id, "CLOSED")

        with pytest.raises(InvitationCompetitionStatusViolation):
            await SendInvitationByEmailUseCase(comp_uow, user_uow).execute(
                SendInvitationByEmailRequestDTO(
                    competition_id=comp.id, inviter_id=creador.id.value, invitee_email="x@test.com"
                )
            )


# ==================== O3 / P1: aceptar ====================


async def _con_handicap(user_uow, email):
    user = User.create(
        first_name="Ana",
        last_name="Prueba",
        email_str=email,
        plain_password="SecureP@ssw0rd123",
        gender=Gender.FEMALE,
    )
    user.update_handicap(14.2)
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _stableford(comp_uow, creador):
    return await CreateCompetitionUseCase(
        comp_uow, LocationBuilder(comp_uow.countries), USUARIOS_CON_GENERO
    ).execute(
        CreateCompetitionRequestDTO(
            name="Medal de octubre",
            start_date=date(2030, 10, 12),
            end_date=date(2030, 10, 12),
            main_country="ES",
            play_mode="HANDICAP",
            tournament_type="STABLEFORD",
            stroke_play=StrokePlaySettingsDTO(category_limits=[Decimal("12.0")]),
        ),
        creador.id,
    )


class TestO3AceptarConLaInscripcionCerrada:
    def test_la_politica_deja_aceptar_cerrada_en_una_ryder(self):
        CompetitionPolicy.can_accept_invitation(CompetitionStatus.CLOSED, stroke_play=False)

    def test_p1_en_un_stroke_play_cerrado_no(self):
        with pytest.raises(InvitationCompetitionStatusViolation, match="reabrir"):
            CompetitionPolicy.can_accept_invitation(CompetitionStatus.CLOSED, stroke_play=True)

    @pytest.mark.parametrize(
        "estado",
        [CompetitionStatus.IN_PROGRESS, CompetitionStatus.COMPLETED, CompetitionStatus.CANCELLED],
    )
    def test_en_juego_o_despues_no(self, estado):
        with pytest.raises(InvitationCompetitionStatusViolation):
            CompetitionPolicy.can_accept_invitation(estado, stroke_play=False)

    async def test_con_sitio_entra(self, comp_uow, user_uow, registro):
        """Given una Ryder cerrada con una pendiente / When la acepta / Then entra."""
        creador = await _usuario(user_uow, "creador@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        invitacion = await _pendiente(comp_uow, comp.id, creador, invitado)
        await set_competition_status(comp_uow, comp.id, "CLOSED")

        respuesta = await _responde(comp_uow, user_uow, invitacion, invitado, registro)

        assert respuesta.status == "ACCEPTED"
        assert await _estado(comp_uow, invitacion) == InvitationStatus.ACCEPTED
        inscripcion = await _inscripcion(comp_uow, comp.id, invitado.id)
        assert inscripcion.status == EnrollmentStatus.APPROVED
        assert await _estado_de_la_competicion(comp_uow, comp.id) == CompetitionStatus.CLOSED
        # Entrar no cierra la suya: no hay aviso de «cerrada»
        assert _cerradas(registro) == []

    async def test_invitado_estando_cerrada_tambien_entra(self, comp_uow, user_uow):
        """O2 + O3: la invitación enviada con la inscripción cerrada se acepta."""
        creador = await _usuario(user_uow, "creador@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        await set_competition_status(comp_uow, comp.id, "CLOSED")
        enviada = await _invita(comp_uow, user_uow, comp.id, creador, invitado)
        async with comp_uow:
            invitacion = await comp_uow.invitations.find_by_id(InvitationId(enviada.id))

        await _responde(comp_uow, user_uow, invitacion, invitado)

        inscripcion = await _inscripcion(comp_uow, comp.id, invitado.id)
        assert inscripcion.status == EnrollmentStatus.APPROVED

    async def test_sin_sitio_sin_plaza_como_hoy(self, comp_uow, user_uow):
        """Given una cerrada de 2 plazas (el organizador ocupa una) y dos pendientes /
        When la primera la llena / Then la segunda se queda sin plaza al aceptar."""
        creador = await _usuario(user_uow, "creador@test.com")
        primero = await _usuario(user_uow, "primero@test.com")
        tarde = await _usuario(user_uow, "tarde@test.com")
        comp = await _competicion(comp_uow, creador, plazas=2)
        la_primera = await _pendiente(comp_uow, comp.id, creador, primero)
        la_tardia = await _pendiente(comp_uow, comp.id, creador, tarde)
        await set_competition_status(comp_uow, comp.id, "CLOSED")
        await _responde(comp_uow, user_uow, la_primera, primero)

        with pytest.raises(InvitationNoRoomViolation):
            await _responde(comp_uow, user_uow, la_tardia, tarde)

        assert await _estado(comp_uow, la_tardia) == InvitationStatus.NO_ROOM
        assert await _inscripcion(comp_uow, comp.id, tarde.id) is None

    async def test_una_pendiente_en_juego_se_queda_sin_plaza(self, comp_uow, user_uow, registro):
        """Una que se colara (no debería: empezar las cierra) no entra a mitad de torneo."""
        creador = await _usuario(user_uow, "creador@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        invitacion = await _pendiente(comp_uow, comp.id, creador, invitado)
        await set_competition_status(comp_uow, comp.id, "IN_PROGRESS")

        with pytest.raises(InvitationNoRoomViolation):
            await _responde(comp_uow, user_uow, invitacion, invitado, registro)

        assert await _estado(comp_uow, invitacion) == InvitationStatus.NO_ROOM
        assert await _inscripcion(comp_uow, comp.id, invitado.id) is None
        assert _cerradas(registro) == [("invitations_closed", [(invitacion.id, invitado.id)])]

    async def test_p1_en_un_stableford_cerrado_no_entra_y_sigue_pendiente(self, comp_uow, user_uow):
        """Given un Stableford cerrado con una pendiente (de antes de cerrar) / When la
        acepta / Then no entra, y la invitación sigue PENDING para cuando lo reabran."""
        creador = await _usuario(user_uow, "creador@test.com")
        invitado = await _con_handicap(user_uow, "invitado@test.com")
        comp = await _stableford(comp_uow, creador)
        invitacion = await _pendiente(comp_uow, comp.id, creador, invitado)
        await set_competition_status(comp_uow, comp.id, "CLOSED")

        with pytest.raises(InvitationCompetitionStatusViolation, match="reabrir"):
            await _responde(comp_uow, user_uow, invitacion, invitado)

        assert await _estado(comp_uow, invitacion) == InvitationStatus.PENDING
        assert await _inscripcion(comp_uow, comp.id, invitado.id) is None

    async def test_p1_en_un_stableford_abierto_entra(self, comp_uow, user_uow):
        creador = await _usuario(user_uow, "creador@test.com")
        invitado = await _con_handicap(user_uow, "invitado@test.com")
        comp = await _stableford(comp_uow, creador)
        invitacion = await _pendiente(comp_uow, comp.id, creador, invitado)

        await _responde(comp_uow, user_uow, invitacion, invitado)

        inscripcion = await _inscripcion(comp_uow, comp.id, invitado.id)
        assert inscripcion.status == EnrollmentStatus.APPROVED


# ==================== P2 / P3: equipos y draft ====================


async def _invitado_a(uow, comp_id):
    """Un usuario de verdad con una invitación pendiente a esa competición."""
    usuarios = UserInMemoryUoW()
    invitado = User.create(
        first_name="Eva",
        last_name="Gil",
        email_str=f"eva_{uuid4().hex[:6]}@example.com",
        plain_password="SecureP@ssw0rd123",
        gender=Gender.FEMALE,
    )
    async with usuarios:
        await usuarios.users.save(invitado)
    async with uow:
        organizador = (await uow.competitions.find_by_id(comp_id)).creator_id
        invitacion = Invitation.create(
            id=InvitationId.generate(),
            competition_id=comp_id,
            inviter_id=organizador,
            invitee_email=str(invitado.email),
            invitee_user_id=invitado.id,
        )
        await uow.invitations.add(invitacion)
        await uow.commit()
    return usuarios, invitado, invitacion


async def _equipos(uow, comp_id):
    async with uow:
        return await uow.team_assignments.find_by_competition(comp_id)


class TestP2EquiposFormados:
    async def test_sin_partidos_entra_y_los_equipos_se_reinician(self):
        """Given una Ryder cerrada con equipos formados y sin partidos / When acepta /
        Then entra, y los equipos se reinician como al aprobar una solicitud."""
        uow, comp_id, *_ = await _montar()
        usuarios, invitado, invitacion = await _invitado_a(uow, comp_id)

        await _responde(uow, usuarios, invitacion, invitado)

        assert (await _inscripcion(uow, comp_id.value, invitado.id)).status == (
            EnrollmentStatus.APPROVED
        )
        assert await _equipos(uow, comp_id) is None

    async def test_con_partidos_no_y_sigue_pendiente(self):
        uow, comp_id, round_id, equipo_a, equipo_b = await _montar()
        await _con_partidos(uow, round_id, equipo_a, equipo_b)
        usuarios, invitado, invitacion = await _invitado_a(uow, comp_id)

        with pytest.raises(TeamsFormedError):
            await _responde(uow, usuarios, invitacion, invitado)

        assert await _estado(uow, invitacion) == InvitationStatus.PENDING
        assert await _inscripcion(uow, comp_id.value, invitado.id) is None
        assert await _equipos(uow, comp_id) is not None


class TestP3NombrarCapitanesYDraft:
    async def test_nombrar_capitanes_deja_las_pendientes(self, comp_uow, user_uow):
        """Given una Ryder abierta con una pendiente / When se nombran capitanes (cierra) /
        Then la pendiente sigue PENDING."""
        creador = await _usuario(user_uow, "creador@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        jugadores = [(await _usuario(user_uow, f"j{i}@test.com")).id for i in range(2)]
        for jugador in jugadores:
            await create_approved_enrollment(comp_uow, comp.id, jugador)
        invitacion = await _pendiente(comp_uow, comp.id, creador, invitado)

        await NameCaptainsUseCase(comp_uow).execute(
            NameCaptainsRequestDTO(
                competition_id=comp.id,
                team_a_captain_id=jugadores[0].value,
                team_b_captain_id=jugadores[1].value,
            ),
            creador.id,
        )

        assert await _estado_de_la_competicion(comp_uow, comp.id) == CompetitionStatus.CLOSED
        assert await _estado(comp_uow, invitacion) == InvitationStatus.PENDING

    async def test_con_la_sala_de_draft_abierta_no_y_sigue_pendiente(self):
        uow, comp_id, *_ = await _montar()
        async with uow:
            competicion = await uow.competitions.find_by_id(comp_id)
            await TeamAssignmentWriter.deshacer(uow, competicion)
            ryder = competicion.ryder_cup
            await uow.drafts.add(
                Draft(
                    id=DraftId.generate(),
                    competition_id=comp_id,
                    team_a_captain_id=ryder.team_a_captain_id,
                    team_b_captain_id=ryder.team_b_captain_id,
                    status=DraftStatus.IN_PROGRESS,
                )
            )
            await uow.commit()
        usuarios, invitado, invitacion = await _invitado_a(uow, comp_id)

        with pytest.raises(DraftInProgressError):
            await _responde(uow, usuarios, invitacion, invitado)

        assert await _estado(uow, invitacion) == InvitationStatus.PENDING
        assert await _inscripcion(uow, comp_id.value, invitado.id) is None


# ==================== O4: cerrar ====================


class TestO4CerrarNoTocaLasInvitaciones:
    async def test_siguen_pendientes_y_sin_aviso(self, comp_uow, user_uow, registro):
        creador = await _usuario(user_uow, "creador@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        invitacion = await _pendiente(comp_uow, comp.id, creador, invitado)

        await CloseEnrollmentsUseCase(comp_uow, actividad=registro).execute(
            CloseEnrollmentsRequestDTO(competition_id=comp.id), creador.id
        )

        assert await _estado_de_la_competicion(comp_uow, comp.id) == CompetitionStatus.CLOSED
        assert await _estado(comp_uow, invitacion) == InvitationStatus.PENDING
        assert _cerradas(registro) == []


# ==================== O5: empezar ====================


async def _pendiente_de(uow, comp_id: CompetitionId, quien_invita: UserId) -> Invitation:
    invitacion = Invitation.create(
        id=InvitationId.generate(),
        competition_id=comp_id,
        inviter_id=quien_invita,
        invitee_email=f"{uuid4().hex[:8]}@test.com",
        invitee_user_id=UserId(uuid4()),
    )
    async with uow:
        await uow.invitations.add(invitacion)
    return invitacion


async def _caducada_de(uow, comp_id: CompetitionId, quien_invita: UserId) -> Invitation:
    caducada = Invitation.reconstruct(
        id=InvitationId.generate(),
        competition_id=comp_id,
        inviter_id=quien_invita,
        invitee_email=f"{uuid4().hex[:8]}@test.com",
        invitee_user_id=UserId(uuid4()),
        status=InvitationStatus.PENDING,
        expires_at=datetime.now() - timedelta(days=1),
    )
    async with uow:
        await uow.invitations.add(caducada)
    return caducada


class TestO5EmpezarCierraLasPendientes:
    async def test_iniciar_a_mano(self, comp_uow, user_uow, registro):
        """Given una Ryder cerrada con una pendiente y una caducada / When se inicia /
        Then la pendiente sin plaza, la caducada caducada, y se retiran sus avisos."""
        creador = await _usuario(user_uow, "creador@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        comp_id = CompetitionId(comp.id)
        pendiente = await _pendiente_de(comp_uow, comp_id, creador.id)
        caducada = await _caducada_de(comp_uow, comp_id, creador.id)
        await set_competition_status(comp_uow, comp.id, "CLOSED")
        async with comp_uow:
            await comp_uow.rounds.add(
                Round.create(
                    competition_id=comp_id,
                    golf_course_id=GolfCourseId(uuid4()),
                    round_date=date(2026, 12, 1),
                    session_type=SessionType.MORNING,
                    match_format=MatchFormat.SINGLES,
                )
            )

        await StartCompetitionUseCase(comp_uow, actividad=registro).execute(
            StartCompetitionRequestDTO(competition_id=comp.id), creador.id
        )

        assert await _estado(comp_uow, pendiente) == InvitationStatus.NO_ROOM
        assert await _estado(comp_uow, caducada) == InvitationStatus.EXPIRED
        (aviso,) = _cerradas(registro)
        assert sorted(aviso[1], key=str) == sorted(
            [
                (pendiente.id, pendiente.invitee_user_id),
                (caducada.id, caducada.invitee_user_id),
            ],
            key=str,
        )

    async def test_el_primer_golpe_de_una_partida(self, registro):
        escenario, partida = await _partida()
        pendiente = await _pendiente_de(
            escenario.uow, escenario.competicion.id, escenario.competicion.creator_id
        )
        quien = partida.user_ids[0]

        await AnotarHoyoDePartidaUseCase(
            uow=escenario.uow,
            zonas=escenario.zonas,
            reloj=lambda: escenario.ahora,
            actividad=registro,
        ).execute(
            partida.id.value,
            1,
            SubmitHoleScoreBodyDTO(
                own_score=4, marked_player_id=str(partida.marcadores.get(quien, quien).value)
            ),
            quien,
        )

        assert await _estado(escenario.uow, pendiente) == InvitationStatus.NO_ROOM
        assert _cerradas(registro) == [
            ("invitations_closed", [(pendiente.id, pendiente.invitee_user_id)])
        ]

    async def test_el_organizador_corrigiendo_un_hoyo(self, registro):
        escenario, partida = await _partida()
        pendiente = await _pendiente_de(
            escenario.uow, escenario.competicion.id, escenario.competicion.creator_id
        )

        await CorregirHoyoDePartidaUseCase(
            uow=escenario.uow,
            zonas=escenario.zonas,
            reloj=lambda: escenario.ahora,
            actividad=registro,
        ).execute(
            partida.id.value,
            partida.user_ids[0].value,
            1,
            CorrectHoleBodyDTO(own_score=4),
            escenario.creador,
            False,
        )

        assert await _estado(escenario.uow, pendiente) == InvitationStatus.NO_ROOM
        assert _cerradas(registro) == [
            ("invitations_closed", [(pendiente.id, pendiente.invitee_user_id)])
        ]

    async def test_el_primer_golpe_de_un_partido_avisa(self, registro):
        uow = CompetitionInMemoryUoW()
        competicion, _r, match, a, b = await _monta(uow, competicion_en_curso=False)
        pendiente = await _pendiente_de(uow, competicion.id, competicion.creator_id)

        await SubmitHoleScoreUseCase(
            uow,
            _UsuariosDeLaVista(),
            ScoringService(),
            _ReposDeCampos(),
            now=lambda: DESPUES,
            actividad=registro,
        ).execute(str(match.id), 1, _body(b), a.user_id)

        assert await _estado(uow, pendiente) == InvitationStatus.NO_ROOM
        assert _cerradas(registro) == [
            ("invitations_closed", [(pendiente.id, pendiente.invitee_user_id)])
        ]

    async def test_despues_no_se_invita(self, comp_uow, user_uow):
        creador = await _usuario(user_uow, "creador@test.com")
        invitado = await _usuario(user_uow, "invitado@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        await set_competition_status(comp_uow, comp.id, "IN_PROGRESS")

        with pytest.raises(InvitationCompetitionStatusViolation):
            await _invita(comp_uow, user_uow, comp.id, creador, invitado)


# ==================== O6: nadie vuelve sin consentir ====================


class TestO6QuienSeRetiroNoVuelveSinConsentir:
    async def _retirado(self, comp_uow, user_uow):
        creador = await _usuario(user_uow, "creador@test.com")
        jugador = await _usuario(user_uow, "jugador@test.com")
        comp = await _competicion(comp_uow, creador, plazas=6)
        inscripcion = await create_approved_enrollment(comp_uow, comp.id, jugador.id)
        await WithdrawEnrollmentUseCase(comp_uow).execute(
            WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), jugador.id
        )
        assert (await _inscripcion(comp_uow, comp.id, jugador.id)).status == (
            EnrollmentStatus.WITHDRAWN
        )
        return creador, jugador, comp, inscripcion

    async def test_aprobar_su_inscripcion_retirada_no_le_devuelve(self, comp_uow, user_uow):
        """Given un jugador retirado / When el organizador «aprueba» su inscripción /
        Then no se puede y sigue WITHDRAWN."""
        creador, jugador, comp, inscripcion = await self._retirado(comp_uow, user_uow)

        with pytest.raises(EnrollmentStateError):
            await HandleEnrollmentUseCase(comp_uow, user_uow.users).execute(
                HandleEnrollmentRequestDTO(enrollment_id=inscripcion.id.value, action="APPROVE"),
                creador.id,
            )

        assert (await _inscripcion(comp_uow, comp.id, jugador.id)).status == (
            EnrollmentStatus.WITHDRAWN
        )

    async def test_invitarle_no_le_devuelve_hasta_que_acepta(self, comp_uow, user_uow):
        creador, jugador, comp, _ = await self._retirado(comp_uow, user_uow)

        enviada = await _invita(comp_uow, user_uow, comp.id, creador, jugador)

        assert (await _inscripcion(comp_uow, comp.id, jugador.id)).status == (
            EnrollmentStatus.WITHDRAWN
        )
        async with comp_uow:
            invitacion = await comp_uow.invitations.find_by_id(InvitationId(enviada.id))
        await _responde(comp_uow, user_uow, invitacion, jugador)
        assert (await _inscripcion(comp_uow, comp.id, jugador.id)).status == (
            EnrollmentStatus.APPROVED
        )


# ==================== P3: la ruta ====================


async def test_p3_la_ruta_responde_409_draft_in_progress_con_su_texto():
    """Given aceptar con la sala de draft abierta / When responde la ruta /
    Then 409 con su código y un texto fijo, no el de la excepción."""

    class _ConLaSalaAbierta:
        async def execute(self, _dto):
            raise DraftInProgressError("CENTINELA-del-draft")

    respuesta = await respond_to_invitation(
        invitation_id=uuid4(),
        body=RespondInvitationBody(action="ACCEPT"),
        current_user=SimpleNamespace(id=uuid4()),
        use_case=_ConLaSalaAbierta(),
    )

    assert respuesta.status_code == 409
    assert json.loads(respuesta.body) == {
        "detail": "Wait until the draft is over.",
        "error_code": "DRAFT_IN_PROGRESS",
    }
