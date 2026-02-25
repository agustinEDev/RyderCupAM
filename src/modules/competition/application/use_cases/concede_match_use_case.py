"""Caso de Uso: Conceder un partido."""

from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    MatchNotFoundError,
    MatchNotScoringError,
    NotMatchPlayerError,
    RoundNotFoundError,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.user.domain.value_objects.user_id import UserId


class ConcedeMatchUseCase:
    """Concede un partido a favor del equipo contrario."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        scoring_service: ScoringService,
    ):
        self._uow = uow
        self._scoring_service = scoring_service

    async def execute(
        self,
        match_id_str: str,
        user_id: UserId,
        conceding_team: str,
        reason: str | None = None,
    ) -> dict:
        async with self._uow:
            match_id = MatchId(match_id_str)
            match = await self._uow.matches.find_by_id(match_id)
            if not match:
                raise MatchNotFoundError(f"No existe partido con ID {match_id_str}")

            if not match.status.can_record_scores():
                raise MatchNotScoringError(
                    f"Partido no esta en estado para conceder. Estado: {match.status.value}"
                )

            round_entity = await self._uow.rounds.find_by_id(match.round_id)
            if not round_entity:
                raise RoundNotFoundError("La ronda asociada no existe")

            competition = await self._uow.competitions.find_by_id(round_entity.competition_id)
            if not competition:
                raise CompetitionNotFoundError("La competicion asociada no existe")

            # Auth: player can only concede own team; creator can concede any
            player_team = match.get_player_team(user_id)
            is_creator = competition.is_creator(user_id)

            if player_team is None and not is_creator:
                raise NotMatchPlayerError(
                    "No eres jugador de este partido ni creador de la competicion"
                )

            if player_team is not None and not is_creator and player_team != conceding_team:
                raise NotMatchPlayerError(
                    "Solo puedes conceder tu propio equipo"
                )

            match.concede(conceding_team, reason)
            await self._uow.matches.update(match)

            # Auto-complete round
            all_matches = await self._uow.matches.find_by_round(match.round_id)
            all_finished = all(m.is_finished() for m in all_matches)
            if all_finished and round_entity.status == RoundStatus.IN_PROGRESS:
                round_entity.complete()
                await self._uow.rounds.update(round_entity)

        return {
            "match_id": str(match.id),
            "new_status": match.status.value,
            "result": match.result,
        }
