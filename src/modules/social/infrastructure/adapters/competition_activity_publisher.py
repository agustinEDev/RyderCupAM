"""Adaptador: `competition` avisa en Actividad a traves del modulo social."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
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
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.social.application.use_cases.publish_competition_notices_use_case import (
    MatchOutcome,
    PublishCompetitionNoticesUseCase,
    StandingRef,
    TournamentRef,
)
from src.modules.user.domain.value_objects.user_id import UserId


class OfficialStandings(Protocol):
    """La general oficial de un stroke play (`ClasificacionGeneralUseCase`)."""

    async def execute(self, competition_id: UUID, categoria: int | None = None): ...


class CompetitionActivityPublisher(CompetitionActivityPublisherInterface):
    """
    Une `competition` con Actividad sin que ninguno importe al otro: el mismo
    reparto que los logros. Aqui solo se traduce; que se publica y para quien lo
    decide `PublishCompetitionNoticesUseCase`.

    **La clasificacion final sale de la general oficial**, la misma que ve
    cualquiera en la ficha del torneo, y no se recalcula: se le pide y se pasa
    tal cual. Solo la tiene un stroke play; una Ryder se juega por equipos y no
    tiene puesto individual que contar.
    """

    def __init__(
        self,
        notices: PublishCompetitionNoticesUseCase,
        standings: OfficialStandings,
        competition_uow: CompetitionUnitOfWorkInterface,
    ):
        self._notices = notices
        self._standings = standings
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

    async def reopened(self, competition_id: CompetitionId) -> None:
        await self._notices.reopened(str(competition_id.value))

    async def made_private(self, competition_id: CompetitionId) -> None:
        await self._notices.tournament_made_private(str(competition_id.value))

    async def deleted(self, competition_id: CompetitionId) -> None:
        await self._notices.tournament_deleted(str(competition_id.value))


def _ref(competition: Competition) -> TournamentRef:
    return TournamentRef(
        competition_id=str(competition.id.value),
        name=str(competition.name),
        start_date=competition.dates.start_date,
        end_date=competition.dates.end_date,
        is_public=competition.visibility == Visibility.PUBLIC,
    )
