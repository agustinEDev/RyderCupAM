"""
Con los equipos formados, quedan así (decidido el 29 oct 2026, tabla aprobada).

Sustituye a mover jugadores sin deshacer los equipos (BE #695, cerrada sin
mergear). Salgan del draft o los forme el organizador, el jugador ya no entra ni
sale por su cuenta; si alguien no puede jugar, el organizador le quita y todo se
reinicia (equipos, sala, sobres y subcapitanes), como desde el 27 oct.

| #  | Quién y qué                                      | Con equipos formados              |
|----|--------------------------------------------------|-----------------------------------|
| J1 | El jugador se retira (también con partidos)      | TEAMS_FORMED                      |
| J2 | El jugador se inscribe en una pública            | TEAMS_FORMED                      |
| J4 | El jugador acepta una invitación                 | TEAMS_FORMED; rechazarla, sí      |
| J5 | El jugador cancela su solicitud pendiente        | Puede                             |
| J6 | Todo lo anterior sin equipos formados            | Como antes                        |
| O1 | El organizador le quita, sin partidos            | Se reinicia todo (test_quitar_inscrito) |
| O2 | El organizador inscribe o aprueba                | Se reinicia todo (test_entrar_deshace_equipos) |
| O4 | El organizador vuelve a formar equipos           | TEAMS_FORMED                      |
| O5 | El organizador forma equipos con la sala abierta | DRAFT_IN_PROGRESS                 |
| O6 | El organizador forma equipos tras un reinicio    | Como la primera vez               |
"""

from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.enrollment_dto import (
    CancelEnrollmentRequestDTO,
    RequestEnrollmentRequestDTO,
    WithdrawEnrollmentRequestDTO,
)
from src.modules.competition.application.dto.invitation_dto import RespondInvitationRequestDTO
from src.modules.competition.application.dto.round_match_dto import AssignTeamsRequestDTO
from src.modules.competition.application.services.baja_de_la_competicion import (
    DraftInProgressError,
)
from src.modules.competition.application.services.equipos_formados import TeamsFormedError
from src.modules.competition.application.services.team_assignment_writer import (
    TeamAssignmentWriter,
)
from src.modules.competition.application.use_cases.assign_teams_use_case import (
    AssignTeamsUseCase,
)
from src.modules.competition.application.use_cases.cancel_enrollment_use_case import (
    CancelEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.request_enrollment_use_case import (
    AlreadyEnrolledError,
    RequestEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.respond_to_invitation_use_case import (
    RespondToInvitationUseCase,
)
from src.modules.competition.application.use_cases.withdraw_enrollment_use_case import (
    WithdrawEnrollmentUseCase,
)
from src.modules.competition.domain.entities.draft import Draft
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.draft_id import DraftId
from src.modules.competition.domain.value_objects.draft_status import DraftStatus
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UsuariosEnMemoria,
)
from src.shared.domain.value_objects.gender import Gender
from tests.unit.modules.competition.application.use_cases.test_deshacer_equipos import (
    _jugador,
    _montar,
)

pytestmark = pytest.mark.asyncio


class _Usuarios:
    async def find_by_id(self, user_id):
        return SimpleNamespace(id=user_id, gender=Gender.MALE, handicap=None, email=None)

    async def find_by_ids(self, user_ids):
        return [await self.find_by_id(u) for u in user_ids]


async def _reabierta(*, publica: bool = False):
    """Equipos formados, sin partidos, y las inscripciones reabiertas."""
    uow, comp_id, round_id, equipo_a, equipo_b = await _montar()
    async with uow:
        competicion = await uow.competitions.find_by_id(comp_id)
        competicion.reopen_enrollments()
        if publica:
            # Pública y por jugar: si no, la fecha la rechaza antes (revisor)
            empieza = date.today() + timedelta(days=30)
            competicion.update_info(
                visibility=Visibility.PUBLIC,
                dates=DateRange(empieza, empieza + timedelta(days=2)),
            )
        await uow.competitions.update(competicion)
        await uow.commit()
    return uow, comp_id, round_id, equipo_a, equipo_b


async def _equipos(uow, comp_id):
    async with uow:
        return await uow.team_assignments.find_by_competition(comp_id)


async def _de(uow, comp_id, jugador) -> Enrollment:
    async with uow:
        return await uow.enrollments.find_by_user_and_competition(jugador, comp_id)


async def _retira(uow, comp_id, jugador):
    inscripcion = await _de(uow, comp_id, jugador)
    return await WithdrawEnrollmentUseCase(uow).execute(
        WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), jugador
    )


class TestJ1Retirarse:
    async def test_con_equipos_formados_no_se_retira(self):
        uow, comp_id, _, _, equipo_b = await _montar()

        with pytest.raises(TeamsFormedError) as error:
            await _retira(uow, comp_id, equipo_b[1])

        assert error.value.error_code == "TEAMS_FORMED"
        assert (await _de(uow, comp_id, equipo_b[1])).status == EnrollmentStatus.APPROVED
        assert await _equipos(uow, comp_id) is not None

    async def test_tampoco_con_partidos(self):
        uow, comp_id, round_id, equipo_a, equipo_b = await _montar()
        async with uow:
            await uow.matches.add(
                Match.create(
                    round_id=round_id,
                    match_number=1,
                    team_a_players=[_jugador(equipo_a[1])],
                    team_b_players=[_jugador(equipo_b[1])],
                )
            )
            await uow.commit()

        with pytest.raises(TeamsFormedError):
            await _retira(uow, comp_id, equipo_b[1])

    async def test_tampoco_el_capitan(self):
        uow, comp_id, _, _, equipo_b = await _montar()

        with pytest.raises(TeamsFormedError):
            await _retira(uow, comp_id, equipo_b[0])

        async with uow:
            competicion = await uow.competitions.find_by_id(comp_id)
        assert competicion.ryder_cup.team_b_captain_id == equipo_b[0]

    async def test_j6_sin_equipos_se_retira_como_antes(self):
        uow, comp_id, _, _, equipo_b = await _montar()
        async with uow:
            competicion = await uow.competitions.find_by_id(comp_id)
            await TeamAssignmentWriter.deshacer(uow, competicion)
            await uow.commit()

        respuesta = await _retira(uow, comp_id, equipo_b[1])

        assert respuesta.status == "WITHDRAWN"


class TestJ2Inscribirse:
    def _pide(self, comp_id, jugador):
        return RequestEnrollmentRequestDTO(competition_id=comp_id.value, user_id=jugador.value)

    async def test_en_una_publica_con_equipos_no_entra(self):
        uow, comp_id, *_ = await _reabierta(publica=True)
        nuevo = UserId(uuid4())

        with pytest.raises(TeamsFormedError):
            await RequestEnrollmentUseCase(uow, _Usuarios()).execute(self._pide(comp_id, nuevo))

        assert await _de(uow, comp_id, nuevo) is None
        assert await _equipos(uow, comp_id) is not None

    async def test_a_quien_ya_esta_se_le_dice_eso(self):
        """Revisor (29 oct 2026): un doble toque no es «equipos formados»."""
        uow, comp_id, _, _, equipo_b = await _reabierta(publica=True)

        with pytest.raises(AlreadyEnrolledError):
            await RequestEnrollmentUseCase(uow, _Usuarios()).execute(
                self._pide(comp_id, equipo_b[1])
            )


class TestJ4Invitacion:
    async def _invitado(self, uow, comp_id):
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

    def _responde(self, invitacion, invitado, accion):
        return RespondInvitationRequestDTO(
            invitation_id=invitacion.id.value, user_id=invitado.id.value, action=accion
        )

    async def test_aceptarla_con_equipos_no(self):
        uow, comp_id, *_ = await _reabierta()
        usuarios, invitado, invitacion = await self._invitado(uow, comp_id)

        with pytest.raises(TeamsFormedError):
            await RespondToInvitationUseCase(uow, usuarios).execute(
                self._responde(invitacion, invitado, "ACCEPT")
            )

        async with uow:
            sigue = await uow.invitations.find_by_id(invitacion.id)
        assert sigue.status == InvitationStatus.PENDING
        assert await _de(uow, comp_id, invitado.id) is None
        assert await _equipos(uow, comp_id) is not None

    async def test_rechazarla_si(self):
        uow, comp_id, *_ = await _reabierta()
        usuarios, invitado, invitacion = await self._invitado(uow, comp_id)

        await RespondToInvitationUseCase(uow, usuarios).execute(
            self._responde(invitacion, invitado, "DECLINE")
        )

        async with uow:
            sigue = await uow.invitations.find_by_id(invitacion.id)
        assert sigue.status == InvitationStatus.DECLINED
        assert await _equipos(uow, comp_id) is not None


class TestJ5CancelarSuSolicitud:
    async def test_puede_y_los_equipos_siguen(self):
        uow, comp_id, *_ = await _reabierta()
        quien = UserId(uuid4())
        solicitud = Enrollment.request(EnrollmentId.generate(), comp_id, quien)
        async with uow:
            await uow.enrollments.add(solicitud)
            await uow.commit()

        await CancelEnrollmentUseCase(uow).execute(
            CancelEnrollmentRequestDTO(enrollment_id=solicitud.id.value), quien
        )

        assert (await _de(uow, comp_id, quien)).status == EnrollmentStatus.CANCELLED
        assert await _equipos(uow, comp_id) is not None


class TestOFormarEquipos:
    async def _organizador(self, uow, comp_id) -> UserId:
        async with uow:
            return (await uow.competitions.find_by_id(comp_id)).creator_id

    def _al_azar(self, comp_id):
        return AssignTeamsRequestDTO(competition_id=comp_id.value, mode="AUTOMATIC")

    async def test_o4_con_equipos_formados_no_se_vuelven_a_formar(self):
        uow, comp_id, _, equipo_a, equipo_b = await _montar()
        organizador = await self._organizador(uow, comp_id)

        with pytest.raises(TeamsFormedError):
            await AssignTeamsUseCase(uow, _Usuarios()).execute(self._al_azar(comp_id), organizador)

        reparto = await _equipos(uow, comp_id)
        assert list(reparto.team_a_player_ids) == equipo_a
        assert list(reparto.team_b_player_ids) == equipo_b

    async def test_o5_con_la_sala_abierta_no_se_forman(self):
        uow, comp_id, *_ = await _montar()
        organizador = await self._organizador(uow, comp_id)
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

        with pytest.raises(DraftInProgressError):
            await AssignTeamsUseCase(uow, _Usuarios()).execute(self._al_azar(comp_id), organizador)

        assert await _equipos(uow, comp_id) is None

    async def test_o6_tras_el_reinicio_se_forman_como_la_primera_vez(self):
        uow, comp_id, *_ = await _montar()
        organizador = await self._organizador(uow, comp_id)
        async with uow:
            competicion = await uow.competitions.find_by_id(comp_id)
            await TeamAssignmentWriter.deshacer(uow, competicion)
            await uow.commit()

        await AssignTeamsUseCase(uow, _Usuarios()).execute(self._al_azar(comp_id), organizador)

        assert await _equipos(uow, comp_id) is not None
