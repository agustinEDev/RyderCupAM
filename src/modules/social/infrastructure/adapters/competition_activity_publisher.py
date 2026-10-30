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
    TeeWindowRef,
    TournamentRef,
)
from src.modules.social.application.use_cases.publish_round_achievements_use_case import (
    PublishRoundAchievementsUseCase,
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
        round_achievements: PublishRoundAchievementsUseCase | None = None,
    ):
        self._notices = notices
        # Para que hereden «campo nuevo» y «primer torneo» de un torneo que se
        # reabre el torneo cerrado o la partida rapida que pasa a ser lo mas
        # antiguo (22 oct 2026)
        self._achievements = achievements
        self._round_achievements = round_achievements
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

    async def joined(
        self,
        competition: Competition,
        enrollment: Enrollment,
        franja: Round | None,
        waiting: bool,
    ) -> None:
        """Al organizador de la competición, que alguien se ha apuntado (A1)."""
        await self._notices.joined(
            competition.creator_id,
            enrollment.user_id,
            _ref(competition),
            str(enrollment.id.value),
            _franja(franja) if franja is not None else None,
            waiting,
            use_real_name=enrollment.use_real_name,
        )

    async def placed_from_waiting_list(
        self, competition: Competition, franja: Round, user_id: UserId
    ) -> None:
        await self._notices.placed_from_waiting_list(user_id, _ref(competition), _franja(franja))

    async def no_place(self, competition: Competition, enrollments: Sequence[Enrollment]) -> None:
        """A cada uno, su «no hubo plaza», por su inscripción (A4)."""
        await self._notices.no_place(
            _ref(competition), [(e.user_id, str(e.id.value)) for e in enrollments]
        )

    async def window_removed(
        self, competition: Competition, franja: Round, enrollment: Enrollment
    ) -> None:
        await self._notices.window_removed(
            enrollment.user_id, _ref(competition), str(enrollment.id.value), _franja(franja)
        )

    async def left(self, competition_id: CompetitionId, user_id: UserId) -> None:
        await self._notices.left(user_id, str(competition_id.value))

    async def cancelled(self, competition_id: CompetitionId) -> None:
        # Sus logros no hay que moverlos: uno cancelado no se cerro nunca, o
        # se reabrio antes y ya los cedio entonces
        await self._notices.tournament_cancelled(str(competition_id.value))

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

    async def removed(self, competition: Competition, enrollment: Enrollment) -> None:
        """Le avisa de que el organizador le ha quitado, con su inscripcion de origen."""
        await self._notices.removed(enrollment.user_id, _ref(competition), str(enrollment.id.value))

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
        # Retira sus logros y, despues, los exclusivos los hereda lo que pasa a
        # ser lo mas antiguo. Al volver a cerrarlo se los vuelve a llevar
        async with self._competition_uow:
            inscritos = await self._competition_uow.enrollments.find_by_competition(competition_id)
        jugadores = [e.user_id for e in inscritos]
        await self._notices.reopened(str(competition_id.value), jugadores)
        await self._ceder_los_exclusivos(competition_id, jugadores)

    async def _ceder_los_exclusivos(
        self, competition_id: CompetitionId, jugadores: list[UserId]
    ) -> None:
        """
        Publica en los herederos SOLO «campo nuevo» y «primer torneo», y solo
        para los jugadores del torneo reabierto
        (`PublishTournamentAchievementsUseCase.heirs_of`): nunca se reejecuta
        ni se sustituye lo demas de otro torneo (revision final, 22 oct 2026).
        Cada uno en su transaccion y bajo los candados de siempre. Con fallo
        seguro: la reapertura ya esta hecha, y lo que falle en uno no para a
        los demas.
        """
        if self._achievements is None:
            return
        try:
            herederos = await self._achievements.heirs_of(str(competition_id.value))
        except Exception:
            logger.warning(
                "Could not find who inherits the achievements of %s", competition_id, exc_info=True
            )
            return
        for torneo in herederos.tournaments:
            try:
                await self._achievements.republish_exclusive(torneo, jugadores)
            except Exception:
                logger.warning(
                    "Could not republish the achievements of tournament %s", torneo, exc_info=True
                )
        if self._round_achievements is None:
            return
        for partida in herederos.quick_matches:
            try:
                await self._round_achievements.republish_new_course(partida)
            except Exception:
                logger.warning(
                    "Could not republish the new course of quick match %s", partida, exc_info=True
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


def _franja(franja: Round) -> TeeWindowRef:
    """La franja como la cuenta un aviso: día, sesión y primera salida."""
    hoja = franja.hoja_de_salidas
    return TeeWindowRef(
        round_id=str(franja.id.value),
        round_date=franja.round_date,
        session_type=franja.session_type.value,
        tee_time=hoja.primera_salida.strftime("%H:%M") if hoja is not None else None,
    )


def _ref(competition: Competition) -> TournamentRef:
    return TournamentRef(
        competition_id=str(competition.id.value),
        name=str(competition.name),
        start_date=competition.dates.start_date,
        end_date=competition.dates.end_date,
        is_public=competition.visibility == Visibility.PUBLIC,
    )
