"""
Tests de donde avisa `competition` a Actividad (BE-2).

Cada caso de uso que cambia algo que Actividad cuenta llama al puerto despues de
guardar, y un fallo al avisar no deshace ni tumba la accion (G27). Que se
publica y para quien lo prueban los tests del modulo social.
"""

import logging
from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CancelCompetitionRequestDTO,
    CompleteCompetitionRequestDTO,
    RevertCompetitionToInProgressRequestDTO,
    StartCompetitionRequestDTO,
)
from src.modules.competition.application.dto.enrollment_dto import (
    DirectEnrollPlayerRequestDTO,
    HandleEnrollmentRequestDTO,
    WithdrawEnrollmentRequestDTO,
)
from src.modules.competition.application.dto.invitation_dto import (
    RespondInvitationRequestDTO,
    SendInvitationByEmailRequestDTO,
    SendInvitationByUserIdRequestDTO,
)
from src.modules.competition.application.dto.partidas_dto import CorrectHoleBodyDTO
from src.modules.competition.application.dto.round_match_dto import (
    DeclareWalkoverRequestDTO,
    UpdateMatchStatusRequestDTO,
)
from src.modules.competition.application.dto.scoring_dto import SubmitHoleScoreBodyDTO
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.application.use_cases.anotar_hoyo_de_partida_use_case import (
    AnotarHoyoDePartidaUseCase,
)
from src.modules.competition.application.use_cases.cancel_competition_use_case import (
    CancelCompetitionUseCase,
)
from src.modules.competition.application.use_cases.cancel_invitation_use_case import (
    CancelInvitationUseCase,
)
from src.modules.competition.application.use_cases.complete_competition_use_case import (
    CompleteCompetitionUseCase,
)
from src.modules.competition.application.use_cases.concede_match_use_case import (
    ConcedeMatchUseCase,
)
from src.modules.competition.application.use_cases.declare_walkover_use_case import (
    DeclareWalkoverUseCase,
)
from src.modules.competition.application.use_cases.direct_enroll_player_use_case import (
    DirectEnrollPlayerUseCase,
)
from src.modules.competition.application.use_cases.handle_enrollment_use_case import (
    HandleEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.organizador_de_partidas_use_case import (
    CorregirHoyoDePartidaUseCase,
)
from src.modules.competition.application.use_cases.respond_to_invitation_use_case import (
    RespondToInvitationUseCase,
)
from src.modules.competition.application.use_cases.revert_competition_to_in_progress_use_case import (
    RevertCompetitionToInProgressUseCase,
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
from src.modules.competition.application.use_cases.submit_scorecard_use_case import (
    SubmitScorecardUseCase,
)
from src.modules.competition.application.use_cases.update_match_status_use_case import (
    UpdateMatchStatusUseCase,
)
from src.modules.competition.application.use_cases.withdraw_enrollment_use_case import (
    WithdrawEnrollmentUseCase,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UserInMemoryUoW,
)
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat
from tests.unit.modules.competition.application.use_cases.helpers import (
    USUARIOS_CON_GENERO,
    create_approved_enrollment,
    create_competition,
    set_competition_status,
)
from tests.unit.modules.competition.application.use_cases.test_anotar_hoyo_de_partida_use_case import (
    _partida,
)
from tests.unit.modules.competition.application.use_cases.test_submit_hole_score_auto_open import (
    DESPUES,
    _body,
    _monta,
    _ReposDeCampos,
)

pytestmark = pytest.mark.asyncio


class _Registro(CompetitionActivityPublisherInterface):
    """Apunta cada aviso: que se llamo y con que."""

    def __init__(self):
        self.avisos: list[tuple] = []

    async def enrolled(self, competition, enrollment, accepted_request):
        self.avisos.append(("enrolled", competition.id, enrollment.user_id, accepted_request))

    async def left(self, competition_id, user_id):
        self.avisos.append(("left", competition_id, user_id))

    async def cancelled(self, competition_id):
        self.avisos.append(("cancelled", competition_id))

    async def invited(self, competition, invitation):
        self.avisos.append(("invited", competition.id, invitation.invitee_user_id))

    async def invitation_withdrawn(self, invitation):
        self.avisos.append(("invitation_withdrawn", invitation.id, invitation.invitee_user_id))

    async def requests_closed(self, competition, enrollments):
        self.avisos.append(
            ("requests_closed", competition.id, sorted(str(e.user_id) for e in enrollments))
        )

    async def request_rejected(self, competition, enrollment):
        self.avisos.append(("request_rejected", competition.id, enrollment.user_id))

    async def match_finished(self, competition, round_, match):
        self.avisos.append(("match_finished", competition.id, match.id, match.status))

    async def completed(self, competition):
        self.avisos.append(("completed", competition.id, competition.status))

    async def reopened(self, competition_id):
        self.avisos.append(("reopened", competition_id))


class _Roto(CompetitionActivityPublisherInterface):
    """El feed caido: cualquier aviso revienta."""

    async def _falla(self, *_args, **_kwargs):
        raise RuntimeError("feed caido")

    enrolled = left = cancelled = invited = invitation_withdrawn = _falla  # type: ignore[assignment]
    requests_closed = request_rejected = match_finished = completed = reopened = _falla  # type: ignore[assignment]


@pytest.fixture
def uow():
    return InMemoryUnitOfWork()


@pytest.fixture
def registro():
    return _Registro()


async def _abierta(uow) -> tuple[CompetitionId, UserId]:
    creator = UserId(uuid4())
    creada = await create_competition(uow, creator)
    return CompetitionId(creada.id), creator


async def _solicitud(uow, competition_id: CompetitionId, user_id: UserId | None = None):
    solicitud = Enrollment.request(
        id=EnrollmentId.generate(),
        competition_id=competition_id,
        user_id=user_id or UserId(uuid4()),
    )
    async with uow:
        await uow.enrollments.add(solicitud)
    return solicitud


async def _usuario(user_uow, email: str) -> User:
    user = User.create(
        first_name="Ana",
        last_name="Lopez",
        email_str=email,
        plain_password="SecureP@ssw0rd123",
        gender=Gender.MALE,
    )
    async with user_uow:
        await user_uow.users.save(user)
    return user


def _jugador() -> MatchPlayer:
    return MatchPlayer.create(
        user_id=UserId.generate(),
        playing_handicap=10,
        tee_color=TeeColor.YELLOW,
        tee_gender=Gender.MALE,
        strokes_received=[],
    )


async def _partido_en_juego(uow) -> tuple[CompetitionId, UserId, Match]:
    competition_id, creator = await _abierta(uow)
    await set_competition_status(uow, competition_id.value, "IN_PROGRESS")
    ronda = Round.create(
        competition_id=competition_id,
        golf_course_id=GolfCourseId(uuid4()),
        round_date=date(2026, 6, 1),
        session_type=SessionType.MORNING,
        match_format=MatchFormat.SINGLES,
    )
    partido = Match.create(
        round_id=ronda.id, match_number=1, team_a_players=[_jugador()], team_b_players=[_jugador()]
    )
    partido.start()
    async with uow:
        await uow.rounds.add(ronda)
        await uow.matches.add(partido)
    return competition_id, creator, partido


class TestInscripciones:
    async def test_a1_aprobar_una_solicitud_avisa_de_aceptada(self, uow, registro):
        competition_id, creator = await _abierta(uow)
        solicitud = await _solicitud(uow, competition_id)

        await HandleEnrollmentUseCase(uow, USUARIOS_CON_GENERO, actividad=registro).execute(
            HandleEnrollmentRequestDTO(enrollment_id=solicitud.id.value, action="APPROVE"),
            creator,
        )

        assert registro.avisos == [("enrolled", competition_id, solicitud.user_id, True)]

    async def test_a6_rechazar_a_mano_avisa_del_rechazo(self, uow, registro):
        competition_id, creator = await _abierta(uow)
        solicitud = await _solicitud(uow, competition_id)

        await HandleEnrollmentUseCase(uow, USUARIOS_CON_GENERO, actividad=registro).execute(
            HandleEnrollmentRequestDTO(enrollment_id=solicitud.id.value, action="REJECT"),
            creator,
        )

        assert registro.avisos == [("request_rejected", competition_id, solicitud.user_id)]

    async def test_a1_aprobar_una_invitacion_no_es_aceptar_una_solicitud(self, uow, registro):
        """Given una inscripcion INVITED / When el organizador la aprueba / Then sin aceptacion."""
        competition_id, creator = await _abierta(uow)
        invitada = Enrollment.invite(
            id=EnrollmentId.generate(), competition_id=competition_id, user_id=UserId(uuid4())
        )
        async with uow:
            await uow.enrollments.add(invitada)

        await HandleEnrollmentUseCase(uow, USUARIOS_CON_GENERO, actividad=registro).execute(
            HandleEnrollmentRequestDTO(enrollment_id=invitada.id.value, action="APPROVE"),
            creator,
        )

        assert registro.avisos == [("enrolled", competition_id, invitada.user_id, False)]

    async def test_a6_retirar_una_invitacion_no_es_rechazar_una_solicitud(self, uow, registro):
        competition_id, creator = await _abierta(uow)
        invitada = Enrollment.invite(
            id=EnrollmentId.generate(), competition_id=competition_id, user_id=UserId(uuid4())
        )
        async with uow:
            await uow.enrollments.add(invitada)

        await HandleEnrollmentUseCase(uow, USUARIOS_CON_GENERO, actividad=registro).execute(
            HandleEnrollmentRequestDTO(enrollment_id=invitada.id.value, action="REJECT"),
            creator,
        )

        assert registro.avisos == []

    async def test_a2_la_inscripcion_directa_avisa_sin_aceptacion(self, uow, registro):
        competition_id, creator = await _abierta(uow)
        jugador = UserId(uuid4())

        await DirectEnrollPlayerUseCase(uow, USUARIOS_CON_GENERO, actividad=registro).execute(
            DirectEnrollPlayerRequestDTO(
                competition_id=competition_id.value, user_id=jugador.value
            ),
            creator,
        )

        assert registro.avisos == [("enrolled", competition_id, jugador, False)]

    async def test_b11_retirarse_avisa(self, uow, registro):
        competition_id, _ = await _abierta(uow)
        jugador = UserId(uuid4())
        inscrito = await create_approved_enrollment(uow, competition_id.value, jugador)

        await WithdrawEnrollmentUseCase(uow, actividad=registro).execute(
            WithdrawEnrollmentRequestDTO(enrollment_id=inscrito.id.value), jugador
        )

        assert registro.avisos == [("left", competition_id, jugador)]

    async def test_b11_cancelar_la_competicion_avisa(self, uow, registro):
        competition_id, creator = await _abierta(uow)

        await CancelCompetitionUseCase(uow, actividad=registro).execute(
            CancelCompetitionRequestDTO(competition_id=competition_id.value), creator
        )

        assert registro.avisos == [("cancelled", competition_id)]

    async def test_a5_empezar_avisa_de_las_solicitudes_cerradas(self, uow, registro):
        competition_id, creator = await _abierta(uow)
        solicitudes = [await _solicitud(uow, competition_id) for _ in range(2)]
        await set_competition_status(uow, competition_id.value, "CLOSED")
        async with uow:
            await uow.rounds.add(
                Round.create(
                    competition_id=competition_id,
                    golf_course_id=GolfCourseId(uuid4()),
                    round_date=date(2026, 6, 1),
                    session_type=SessionType.MORNING,
                    match_format=MatchFormat.SINGLES,
                )
            )

        await StartCompetitionUseCase(uow, actividad=registro).execute(
            StartCompetitionRequestDTO(competition_id=competition_id.value), creator
        )

        assert registro.avisos == [
            ("requests_closed", competition_id, sorted(str(s.user_id) for s in solicitudes))
        ]

    async def test_a5_sin_solicitudes_pendientes_no_avisa(self, uow, registro):
        competition_id, creator = await _abierta(uow)
        await set_competition_status(uow, competition_id.value, "CLOSED")
        async with uow:
            await uow.rounds.add(
                Round.create(
                    competition_id=competition_id,
                    golf_course_id=GolfCourseId(uuid4()),
                    round_date=date(2026, 6, 1),
                    session_type=SessionType.MORNING,
                    match_format=MatchFormat.SINGLES,
                )
            )

        await StartCompetitionUseCase(uow, actividad=registro).execute(
            StartCompetitionRequestDTO(competition_id=competition_id.value), creator
        )

        assert registro.avisos == []

    async def test_a5_el_primer_golpe_de_un_partido_avisa(self, uow, registro):
        """A5. Given una Ryder cerrada con una solicitud / When el primer golpe la arranca."""
        competicion, _r, match, a, b = await _monta(uow, competicion_en_curso=False)
        solicitud = await _solicitud(uow, competicion.id)

        caso = SubmitHoleScoreUseCase(
            uow,
            _UsuariosDeLaVista(),
            ScoringService(),
            _ReposDeCampos(),
            now=lambda: DESPUES,
            actividad=registro,
        )
        await caso.execute(str(match.id), 1, _body(b), a.user_id)

        assert registro.avisos == [("requests_closed", competicion.id, [str(solicitud.user_id)])]

    async def test_a5_el_primer_golpe_de_una_partida_avisa(self, registro):
        escenario, partida = await _partida()
        solicitud = await _solicitud(escenario.uow, escenario.competicion.id)
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

        assert registro.avisos == [
            ("requests_closed", escenario.competicion.id, [str(solicitud.user_id)])
        ]

    async def test_a5_el_organizador_corrigiendo_avisa(self, registro):
        escenario, partida = await _partida()
        solicitud = await _solicitud(escenario.uow, escenario.competicion.id)

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

        assert registro.avisos == [
            ("requests_closed", escenario.competicion.id, [str(solicitud.user_id)])
        ]


class _UsuariosDeLaVista:
    """Lo que pide la vista de anotacion que devuelve el golpe."""

    async def find_by_id(self, uid):
        user = MagicMock()
        user.first_name = "Player"
        user.last_name = str(uid)[:8]
        user.display_name = f"Player {str(uid)[:8]}"
        user.display_name_or_legal = MagicMock(return_value=f"Player {str(uid)[:8]}")
        return user


class TestInvitaciones:
    @pytest.fixture
    def user_uow(self):
        return UserInMemoryUoW()

    async def test_a3_invitar_por_usuario_avisa(self, uow, user_uow, registro):
        creador = await _usuario(user_uow, "org@test.com")
        invitado = await _usuario(user_uow, "inv@test.com")
        competition_id = CompetitionId((await create_competition(uow, creador.id)).id)

        await SendInvitationByUserIdUseCase(uow, user_uow, actividad=registro).execute(
            SendInvitationByUserIdRequestDTO(
                competition_id=competition_id.value,
                inviter_id=creador.id.value,
                invitee_user_id=invitado.id.value,
            )
        )

        assert registro.avisos == [("invited", competition_id, invitado.id)]

    async def test_a3_invitar_por_correo_a_quien_tiene_cuenta_avisa(self, uow, user_uow, registro):
        creador = await _usuario(user_uow, "org@test.com")
        invitado = await _usuario(user_uow, "inv@test.com")
        competition_id = CompetitionId((await create_competition(uow, creador.id)).id)

        await SendInvitationByEmailUseCase(uow, user_uow, actividad=registro).execute(
            SendInvitationByEmailRequestDTO(
                competition_id=competition_id.value,
                inviter_id=creador.id.value,
                invitee_email="inv@test.com",
            )
        )

        assert registro.avisos == [("invited", competition_id, invitado.id)]

    async def test_a3_invitar_por_correo_a_quien_no_tiene_cuenta_no_avisa(
        self, uow, user_uow, registro
    ):
        creador = await _usuario(user_uow, "org@test.com")
        competition_id = CompetitionId((await create_competition(uow, creador.id)).id)

        await SendInvitationByEmailUseCase(uow, user_uow, actividad=registro).execute(
            SendInvitationByEmailRequestDTO(
                competition_id=competition_id.value,
                inviter_id=creador.id.value,
                invitee_email="nadie@test.com",
            )
        )

        assert registro.avisos == []

    async def _invitacion(self, uow, competition_id, inviter, invitado: User | None):
        invitacion = Invitation.create(
            id=InvitationId.generate(),
            competition_id=competition_id,
            inviter_id=inviter,
            invitee_email="inv@test.com" if invitado else "nadie@test.com",
            invitee_user_id=invitado.id if invitado else None,
        )
        async with uow:
            await uow.invitations.add(invitacion)
        return invitacion

    async def test_a4_retirar_la_invitacion_avisa(self, uow, user_uow, registro):
        creador = await _usuario(user_uow, "org@test.com")
        invitado = await _usuario(user_uow, "inv@test.com")
        competition_id = CompetitionId((await create_competition(uow, creador.id)).id)
        invitacion = await self._invitacion(uow, competition_id, creador.id, invitado)

        await CancelInvitationUseCase(uow, actividad=registro).execute(
            invitacion.id.value, creador.id.value
        )

        assert registro.avisos == [("invitation_withdrawn", invitacion.id, invitado.id)]

    async def test_a4_retirar_la_de_quien_no_tiene_cuenta_no_avisa(self, uow, user_uow, registro):
        creador = await _usuario(user_uow, "org@test.com")
        competition_id = CompetitionId((await create_competition(uow, creador.id)).id)
        invitacion = await self._invitacion(uow, competition_id, creador.id, None)

        await CancelInvitationUseCase(uow, actividad=registro).execute(
            invitacion.id.value, creador.id.value
        )

        assert registro.avisos == []

    async def test_b8_aceptar_una_invitacion_avisa_sin_aceptacion(self, uow, user_uow, registro):
        creador = await _usuario(user_uow, "org@test.com")
        invitado = await _usuario(user_uow, "inv@test.com")
        competition_id = CompetitionId((await create_competition(uow, creador.id)).id)
        invitacion = await self._invitacion(uow, competition_id, creador.id, invitado)

        await RespondToInvitationUseCase(uow, user_uow, actividad=registro).execute(
            RespondInvitationRequestDTO(
                invitation_id=invitacion.id.value, user_id=invitado.id.value, action="ACCEPT"
            )
        )

        assert registro.avisos == [("enrolled", competition_id, invitado.id, False)]

    async def test_declinar_no_avisa(self, uow, user_uow, registro):
        creador = await _usuario(user_uow, "org@test.com")
        invitado = await _usuario(user_uow, "inv@test.com")
        competition_id = CompetitionId((await create_competition(uow, creador.id)).id)
        invitacion = await self._invitacion(uow, competition_id, creador.id, invitado)

        await RespondToInvitationUseCase(uow, user_uow, actividad=registro).execute(
            RespondInvitationRequestDTO(
                invitation_id=invitacion.id.value, user_id=invitado.id.value, action="DECLINE"
            )
        )

        assert registro.avisos == []


class TestPartidos:
    async def test_c13_conceder_avisa(self, uow, registro):
        competition_id, creator, partido = await _partido_en_juego(uow)

        await ConcedeMatchUseCase(uow, ScoringService(), actividad=registro).execute(
            str(partido.id), creator, "A"
        )

        assert registro.avisos == [
            ("match_finished", competition_id, partido.id, MatchStatus.CONCEDED)
        ]

    async def test_c13_walkover_avisa(self, uow, registro):
        competition_id, creator, partido = await _partido_en_juego(uow)

        await DeclareWalkoverUseCase(uow, actividad=registro).execute(
            DeclareWalkoverRequestDTO(match_id=partido.id.value, winning_team="B"), creator
        )

        assert registro.avisos == [
            ("match_finished", competition_id, partido.id, MatchStatus.WALKOVER)
        ]

    async def test_c13_cerrarlo_el_organizador_avisa(self, uow, registro):
        competition_id, creator, partido = await _partido_en_juego(uow)

        await UpdateMatchStatusUseCase(uow, actividad=registro).execute(
            UpdateMatchStatusRequestDTO(
                match_id=partido.id.value, action="COMPLETE", result={"winner": "A", "score": "2UP"}
            ),
            creator,
        )

        assert registro.avisos == [
            ("match_finished", competition_id, partido.id, MatchStatus.COMPLETED)
        ]

    async def test_empezar_un_partido_no_avisa(self, uow, registro):
        competition_id, creator = await _abierta(uow)
        await set_competition_status(uow, competition_id.value, "IN_PROGRESS")
        ronda = Round.create(
            competition_id=competition_id,
            golf_course_id=GolfCourseId(uuid4()),
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        partido = Match.create(
            round_id=ronda.id,
            match_number=1,
            team_a_players=[_jugador()],
            team_b_players=[_jugador()],
        )
        async with uow:
            await uow.rounds.add(ronda)
            await uow.matches.add(partido)

        await UpdateMatchStatusUseCase(uow, actividad=registro).execute(
            UpdateMatchStatusRequestDTO(match_id=partido.id.value, action="START"), creator
        )

        assert registro.avisos == []

    async def test_c13_la_ultima_tarjeta_avisa_y_la_primera_no(self, uow, registro):
        competition_id, _creator, partido = await _partido_en_juego(uow)
        caso = SubmitScorecardUseCase(uow, ScoringService(), actividad=registro)
        a = partido.team_a_players[0].user_id
        b = partido.team_b_players[0].user_id

        await caso.execute(str(partido.id), a)
        assert registro.avisos == []
        await caso.execute(str(partido.id), b)

        assert registro.avisos == [
            ("match_finished", competition_id, partido.id, MatchStatus.COMPLETED)
        ]


class TestCompeticion:
    async def test_c14_terminar_avisa_con_la_competicion_ya_terminada(self, uow, registro):
        competition_id, creator = await _abierta(uow)
        await set_competition_status(uow, competition_id.value, "IN_PROGRESS")

        await CompleteCompetitionUseCase(uow, actividad=registro).execute(
            CompleteCompetitionRequestDTO(competition_id=competition_id.value), creator
        )

        assert registro.avisos == [("completed", competition_id, CompetitionStatus.COMPLETED)]

    async def test_c15_reabrir_avisa(self, uow, registro):
        competition_id, creator = await _abierta(uow)
        await set_competition_status(uow, competition_id.value, "COMPLETED")

        await RevertCompetitionToInProgressUseCase(uow, actividad=registro).execute(
            RevertCompetitionToInProgressRequestDTO(competition_id=competition_id.value), creator
        )

        assert registro.avisos == [("reopened", competition_id)]


class TestG27UnFalloAlAvisarNoTumbaLaAccion:
    async def test_aprobar_sigue_aprobado(self, uow, caplog):
        competition_id, creator = await _abierta(uow)
        solicitud = await _solicitud(uow, competition_id)

        with caplog.at_level(logging.WARNING):
            respuesta = await HandleEnrollmentUseCase(
                uow, USUARIOS_CON_GENERO, actividad=_Roto()
            ).execute(
                HandleEnrollmentRequestDTO(enrollment_id=solicitud.id.value, action="APPROVE"),
                creator,
            )

        assert respuesta.status == "APPROVED"
        async with uow:
            guardada = await uow.enrollments.find_by_id(solicitud.id)
        assert guardada.status == EnrollmentStatus.APPROVED
        assert any(
            r.levelno == logging.WARNING and "activity" in r.getMessage().lower()
            for r in caplog.records
        )

    async def test_conceder_sigue_concedido(self, uow, caplog):
        _competition_id, creator, partido = await _partido_en_juego(uow)

        with caplog.at_level(logging.WARNING):
            resultado = await ConcedeMatchUseCase(uow, ScoringService(), actividad=_Roto()).execute(
                str(partido.id), creator, "A"
            )

        assert resultado["new_status"] == MatchStatus.CONCEDED.value
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    async def test_terminar_sigue_terminada(self, uow):
        competition_id, creator = await _abierta(uow)
        await set_competition_status(uow, competition_id.value, "IN_PROGRESS")

        respuesta = await CompleteCompetitionUseCase(uow, actividad=_Roto()).execute(
            CompleteCompetitionRequestDTO(competition_id=competition_id.value), creator
        )

        assert respuesta.status == CompetitionStatus.COMPLETED.value

    async def test_empezar_sigue_empezada(self, uow):
        competition_id, creator = await _abierta(uow)
        await _solicitud(uow, competition_id)
        await set_competition_status(uow, competition_id.value, "CLOSED")
        async with uow:
            await uow.rounds.add(
                Round.create(
                    competition_id=competition_id,
                    golf_course_id=GolfCourseId(uuid4()),
                    round_date=date(2026, 6, 1),
                    session_type=SessionType.MORNING,
                    match_format=MatchFormat.SINGLES,
                )
            )

        respuesta = await StartCompetitionUseCase(uow, actividad=_Roto()).execute(
            StartCompetitionRequestDTO(competition_id=competition_id.value), creator
        )

        assert respuesta.status == CompetitionStatus.IN_PROGRESS.value

    async def test_retirarse_sigue_retirado(self, uow):
        competition_id, _ = await _abierta(uow)
        jugador = UserId(uuid4())
        inscrito = await create_approved_enrollment(uow, competition_id.value, jugador)

        respuesta = await WithdrawEnrollmentUseCase(uow, actividad=_Roto()).execute(
            WithdrawEnrollmentRequestDTO(enrollment_id=inscrito.id.value), jugador
        )

        assert respuesta.status == EnrollmentStatus.WITHDRAWN.value
