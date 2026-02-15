"""Caso de Uso: Declarar walkover en un partido."""

from src.modules.competition.application.dto.round_match_dto import (
    DeclareWalkoverRequestDTO,
    DeclareWalkoverResponseDTO,
)
from src.modules.competition.application.exceptions import (
    MatchNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.user.domain.value_objects.user_id import UserId


class CompetitionNotInProgressError(Exception):
    """La competicion no esta en progreso."""

    pass


class InvalidWalkoverError(Exception):
    """No se puede declarar walkover en el estado actual."""

    pass


class DeclareWalkoverUseCase:
    """
    Caso de uso para declarar walkover (victoria por incomparecencia).

    Transicion: SCHEDULED o IN_PROGRESS -> WALKOVER
    Auto-complete round si todos los partidos terminaron.
    La competicion debe estar IN_PROGRESS.
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(
        self, request: DeclareWalkoverRequestDTO, user_id: UserId
    ) -> DeclareWalkoverResponseDTO:
        async with self._uow:
            # 1. Buscar el partido
            match_id = MatchId(request.match_id)
            match = await self._uow.matches.find_by_id(match_id)

            if not match:
                raise MatchNotFoundError(f"No existe partido con ID {request.match_id}")

            # 2. Buscar ronda y competicion
            round_entity = await self._uow.rounds.find_by_id(match.round_id)
            if not round_entity:
                raise MatchNotFoundError("La ronda asociada no existe")

            competition = await self._uow.competitions.find_by_id(round_entity.competition_id)
            if not competition:
                raise MatchNotFoundError("La competicion asociada no existe")

            # 3. Verificar creador
            if not competition.is_creator(user_id):
                raise NotCompetitionCreatorError("Solo el creador puede declarar walkover")

            # 4. Verificar competicion IN_PROGRESS
            if not competition.is_in_progress():
                raise CompetitionNotInProgressError(
                    f"La competicion debe estar IN_PROGRESS. Estado: {competition.status.value}"
                )

            # 5. Declarar walkover
            try:
                match.declare_walkover(request.winning_team, request.reason)
            except ValueError as e:
                raise InvalidWalkoverError(str(e)) from e

            await self._uow.matches.update(match)

            # 6. Auto-complete round si todos terminaron
            round_status_changed = None
            all_matches = await self._uow.matches.find_by_round(match.round_id)
            all_finished = all(m.is_finished() for m in all_matches)
            if all_finished and round_entity.status == RoundStatus.IN_PROGRESS:
                round_entity.complete()
                await self._uow.rounds.update(round_entity)
                round_status_changed = round_entity.status.value

        return DeclareWalkoverResponseDTO(
            match_id=match.id.value,
            new_status=match.status.value,
            winning_team=request.winning_team,
            round_status=round_status_changed,
            updated_at=match.updated_at,
        )
