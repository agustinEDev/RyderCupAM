"""Adaptador: `competition` avisa en Actividad a traves del modulo social."""

import logging
from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
    TeeTimeAssignment,
)
from src.modules.competition.application.services.salidas_de_la_ronda import salidas_vigentes
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.social.application.use_cases.publish_competition_notices_use_case import (
    MatchOutcome,
    PublishCompetitionNoticesUseCase,
    RyderResultRef,
    StandingRef,
    TeeTimeRef,
    TournamentRef,
)
from src.modules.social.application.use_cases.publish_tournament_achievements_use_case import (
    PublishTournamentAchievementsUseCase,
)
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)


class OfficialStandings(Protocol):
    """La general oficial de un stroke play (`ClasificacionGeneralUseCase`)."""

    async def execute(self, competition_id: UUID, categoria: int | None = None): ...


class RyderScoreboard(Protocol):
    """El leaderboard oficial de una Ryder (`GetLeaderboardUseCase`)."""

    async def execute(self, competition_id_str: str): ...


class CompetitionActivityPublisher(CompetitionActivityPublisherInterface):
    """
    Une `competition` con Actividad sin que ninguno importe al otro: el mismo
    reparto que los logros. Aqui solo se traduce; que se publica y para quien lo
    decide `PublishCompetitionNoticesUseCase`.

    **La clasificacion final sale de la general oficial**, la misma que ve
    cualquiera en la ficha del torneo, y no se recalcula: se le pide y se pasa
    tal cual. **La de una Ryder sale de su leaderboard oficial** (tabla del 22
    oct 2026, I): los mismos puntos que ve cualquiera, sin otra cuenta; los
    equipos, de la asignacion de equipos mas quien jugo algun partido.
    """

    def __init__(
        self,
        notices: PublishCompetitionNoticesUseCase,
        standings: OfficialStandings,
        competition_uow: CompetitionUnitOfWorkInterface,
        ryder_scoreboard: RyderScoreboard | None = None,
        achievements: PublishTournamentAchievementsUseCase | None = None,
    ):
        self._notices = notices
        # Para volver a publicar los torneos del mismo dia que dependen de uno
        # que se cancela (revision final de bugs, 22 oct 2026)
        self._achievements = achievements
        self._standings = standings
        self._ryder_scoreboard = ryder_scoreboard
        # Para releer la inscripcion justo antes de avisar de ella
        self._competition_uow = competition_uow

    async def enrolled(
        self, competition: Competition, enrollment: Enrollment, accepted_request: bool
    ) -> None:
        # Se relee justo antes de publicar: si entre guardarla y avisar se
        # retiro, su aviso llegaria tarde y nadie lo retiraria ya
        async with self._competition_uow:
            actual = await self._competition_uow.enrollments.find_by_id(enrollment.id)
        if actual is None or actual.status != EnrollmentStatus.APPROVED:
            return
        await self._notices.enrolled(
            enrollment.user_id, _ref(competition), str(enrollment.id.value), accepted_request
        )

    async def left(self, competition_id: CompetitionId, user_id: UserId) -> None:
        await self._notices.left(user_id, str(competition_id.value))

    async def cancelled(self, competition_id: CompetitionId) -> None:
        await self._notices.tournament_cancelled(str(competition_id.value))
        await self._republicar_los_del_mismo_dia(competition_id)

    async def invited(self, competition: Competition, invitation: Invitation) -> None:
        if invitation.invitee_user_id is None:
            return
        await self._notices.invited(
            invitation.invitee_user_id, _ref(competition), str(invitation.id.value)
        )

    async def invitation_withdrawn(self, invitation: Invitation) -> None:
        if invitation.invitee_user_id is None:
            return
        await self._notices.invitation_withdrawn(
            invitation.invitee_user_id, str(invitation.id.value)
        )

    async def invitation_answered(self, invitation: Invitation) -> None:
        if invitation.invitee_user_id is None:
            return
        await self._notices.invitation_answered(
            invitation.invitee_user_id, str(invitation.id.value)
        )

    async def invitations_closed(self, invitations: Sequence[Invitation]) -> None:
        await self._notices.invitations_closed(
            [
                (i.invitee_user_id, str(i.id.value))
                for i in invitations
                if i.invitee_user_id is not None
            ]
        )

    async def requests_closed(
        self, competition: Competition, enrollments: Sequence[Enrollment]
    ) -> None:
        await self._notices.requests_closed(
            _ref(competition), [(e.user_id, str(e.id.value)) for e in enrollments]
        )

    async def request_rejected(self, competition: Competition, enrollment: Enrollment) -> None:
        await self._notices.request_rejected(
            enrollment.user_id, _ref(competition), str(enrollment.id.value)
        )

    async def match_finished(self, competition: Competition, round_: Round, match: Match) -> None:
        resultado = match.result or {}
        await self._notices.match_finished(
            _ref(competition),
            MatchOutcome(
                match_id=str(match.id.value),
                # Una ronda vieja sin fecha: el primer dia del torneo
                played_on=round_.round_date or competition.dates.start_date,
                team_a=tuple(p.user_id for p in match.team_a_players),
                team_b=tuple(p.user_id for p in match.team_b_players),
                winner=resultado.get("winner"),
                score=resultado.get("score"),
            ),
        )

    async def completed(self, competition: Competition) -> None:
        if competition.stroke_play is None:
            await self._ryder_completed(competition)
            return
        general = await self._standings.execute(competition.id.value, None)
        await self._notices.final_standings(
            _ref(competition),
            general.tournament_type,
            [
                StandingRef(
                    user_id=UserId(fila.user_id),
                    position=fila.position,
                    tied=fila.tied,
                    value=fila.value,
                    status=fila.status,
                )
                for fila in general.rows
            ],
        )

    async def _ryder_completed(self, competition: Competition) -> None:
        """El marcador del leaderboard oficial y quien jugo en cada equipo."""
        if self._ryder_scoreboard is None:
            return
        marcador = await self._ryder_scoreboard.execute(str(competition.id.value))
        async with self._competition_uow:
            asignacion = await self._competition_uow.team_assignments.find_by_competition(
                competition.id
            )
        equipo_a = list(asignacion.team_a_player_ids) if asignacion else []
        equipo_b = list(asignacion.team_b_player_ids) if asignacion else []
        # Quien jugo un partido sin estar en la asignacion (un cambio de
        # jugador) tambien acabo el torneo con su equipo
        for partido in marcador.matches:
            for jugadores, equipo in (
                (partido.team_a_players, equipo_a),
                (partido.team_b_players, equipo_b),
            ):
                for jugador in jugadores:
                    user_id = UserId(jugador.user_id)
                    if user_id not in equipo_a and user_id not in equipo_b:
                        equipo.append(user_id)
        await self._notices.ryder_final_result(
            _ref(competition),
            RyderResultRef(
                team_a_name=marcador.team_a_name,
                team_b_name=marcador.team_b_name,
                team_a_points=marcador.team_a_points,
                team_b_points=marcador.team_b_points,
                team_a=tuple(equipo_a),
                team_b=tuple(equipo_b),
            ),
        )

    async def reopened(self, competition_id: CompetitionId) -> None:
        # No hace falta volver a publicar los del mismo dia: uno reabierto sigue
        # contando para ellos como cuando estaba cerrado. Lo que se corrija
        # mientras, lo recogen el nuevo cierre o la cancelacion
        await self._notices.reopened(str(competition_id.value))

    async def _republicar_los_del_mismo_dia(self, competition_id: CompetitionId) -> None:
        """
        «Campo nuevo» y «primer torneo» de los torneos cerrados del mismo dia
        dependen de este: al cancelarlo deja de contar y se vuelven a publicar. Con fallo seguro: el aviso
        propio ya salio y la accion no falla por esto.
        """
        if self._achievements is None:
            return
        try:
            await self._achievements.republish_same_day(str(competition_id.value))
        except Exception:
            logger.warning(
                "Could not republish the same-day tournaments of %s", competition_id, exc_info=True
            )

    async def made_private(self, competition_id: CompetitionId) -> None:
        await self._notices.tournament_made_private(str(competition_id.value))

    async def deleted(self, competition_id: CompetitionId) -> None:
        await self._notices.tournament_deleted(str(competition_id.value))

    async def round_deleted(self, competition_id: CompetitionId, round_id: RoundId) -> None:
        await self._notices.round_deleted(str(competition_id.value), str(round_id.value))

    async def tee_times(
        self,
        competition: Competition,
        round_id: RoundId,
        assigned: Sequence[TeeTimeAssignment],
        withdrawn: Sequence[UserId],
    ) -> None:
        # Lo que trae la accion (`assigned`, `withdrawn`) solo dice que la ronda
        # cambio: se publica lo que hay ahora, releido con el torneo bloqueado.
        # Dos publicaciones de la misma ronda pueden llegar en cualquier orden
        # (cada una tras su commit, en su sesion), y la ultima en llegar podria
        # ser la de una foto vieja (revision del 22 oct 2026)
        async def _vigentes() -> list[TeeTimeRef]:
            salidas = await salidas_vigentes(self._competition_uow, round_id)
            return [
                TeeTimeRef(
                    user_id=salida.user_id,
                    round_date=salida.round_date,
                    session_type=salida.session_type.value,
                    tee_time=salida.tee_time.strftime("%H:%M") if salida.tee_time else None,
                    partner_ids=salida.partner_ids,
                    opponent_ids=salida.opponent_ids,
                    match_id=str(salida.match_id.value) if salida.match_id else None,
                    out_of_play=salida.out_of_play,
                )
                for salida in salidas.values()
            ]

        await self._notices.tee_times(_ref(competition), str(round_id.value), _vigentes)


def _ref(competition: Competition) -> TournamentRef:
    return TournamentRef(
        competition_id=str(competition.id.value),
        name=str(competition.name),
        start_date=competition.dates.start_date,
        end_date=competition.dates.end_date,
        is_public=competition.visibility == Visibility.PUBLIC,
    )
