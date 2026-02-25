"""Caso de Uso: Actualizar estado de un partido."""

from src.modules.competition.application.dto.round_match_dto import (
    UpdateMatchStatusRequestDTO,
    UpdateMatchStatusResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    MatchNotFoundError,
    NotCompetitionCreatorError,
    RoundNotFoundError,
)
from src.modules.competition.domain.entities.hole_score import HoleScore
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.user.domain.value_objects.user_id import UserId


class CompetitionNotInProgressError(Exception):
    """La competicion no esta en progreso."""

    pass


class InvalidActionError(Exception):
    """Accion invalida para el estado actual del partido."""

    pass


class UpdateMatchStatusUseCase:
    """
    Caso de uso para actualizar el estado de un partido.

    Acciones:
    - START: SCHEDULED -> IN_PROGRESS (auto-start round si esta SCHEDULED)
    - COMPLETE: IN_PROGRESS -> COMPLETED (auto-complete round si todos terminaron)

    La competicion debe estar IN_PROGRESS.
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(
        self, request: UpdateMatchStatusRequestDTO, user_id: UserId
    ) -> UpdateMatchStatusResponseDTO:
        async with self._uow:
            # 1-4. Validaciones
            match, round_entity = await self._validate(request, user_id)

            # 5. Ejecutar accion
            if request.action == "START":
                round_status_changed = await self._handle_start(match, round_entity)
            elif request.action == "COMPLETE":
                round_status_changed = await self._handle_complete(request, match, round_entity)
            else:
                raise InvalidActionError(f"Accion invalida: {request.action}. Use START o COMPLETE")

            if round_status_changed:
                await self._uow.rounds.update(round_entity)
            await self._uow.matches.update(match)

        return UpdateMatchStatusResponseDTO(
            match_id=match.id.value,
            new_status=match.status.value,
            round_status=round_status_changed,
            updated_at=match.updated_at,
        )

    async def _validate(self, request, user_id):
        """Validaciones: buscar match, ronda, competicion, verificar creador y estado."""
        match_id = MatchId(request.match_id)
        match = await self._uow.matches.find_by_id(match_id)

        if not match:
            raise MatchNotFoundError(f"No existe partido con ID {request.match_id}")

        round_entity = await self._uow.rounds.find_by_id(match.round_id)
        if not round_entity:
            raise RoundNotFoundError("La ronda asociada no existe")

        competition = await self._uow.competitions.find_by_id(round_entity.competition_id)
        if not competition:
            raise CompetitionNotFoundError("La competicion asociada no existe")

        if not competition.is_creator(user_id):
            raise NotCompetitionCreatorError("Solo el creador puede actualizar partidos")

        if not competition.is_in_progress():
            raise CompetitionNotInProgressError(
                f"La competicion debe estar IN_PROGRESS. Estado: {competition.status.value}"
            )

        return match, round_entity

    async def _handle_start(self, match, round_entity):
        """Ejecuta START: match.start() + auto-start round + pre-create HoleScores."""
        try:
            match.start()
        except ValueError as e:
            raise InvalidActionError(str(e)) from e

        # Pre-create 18 HoleScores per player (empty, ready for scoring)
        hole_scores = []
        for team, players in [("A", match.team_a_players), ("B", match.team_b_players)]:
            for player in players:
                for hole_num in range(1, 19):
                    strokes_received = player.strokes_on_hole(hole_num)
                    hs = HoleScore.create(
                        match_id=match.id,
                        hole_number=hole_num,
                        player_user_id=player.user_id,
                        team=team,
                        strokes_received=strokes_received,
                    )
                    hole_scores.append(hs)
        await self._uow.hole_scores.add_many(hole_scores)

        if round_entity.status == RoundStatus.SCHEDULED:
            round_entity.start()
            return round_entity.status.value
        return None

    async def _handle_complete(self, request, match, round_entity):
        """Ejecuta COMPLETE: match.complete() + auto-complete round."""
        if request.result is None:
            raise InvalidActionError("Se requiere 'result' para completar un partido")
        try:
            match.complete(request.result)
        except ValueError as e:
            raise InvalidActionError(str(e)) from e

        # Persist match status before querying so find_by_round sees the update
        await self._uow.matches.update(match)

        all_matches = await self._uow.matches.find_by_round(match.round_id)
        all_finished = all(m.is_finished() for m in all_matches)
        if all_finished and round_entity.status == RoundStatus.IN_PROGRESS:
            round_entity.complete()
            return round_entity.status.value
        return None
