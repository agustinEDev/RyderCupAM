"""Caso de Uso: Registrar/actualizar el score propio de un hoyo."""

from src.modules.quick_match.application.dto.quick_match_dto import (
    HoleScoreResponseDTO,
    SubmitHoleScoreRequestDTO,
)
from src.modules.quick_match.application.exceptions import (
    NotQuickMatchParticipantError,
    QuickMatchNotFoundError,
)
from src.modules.quick_match.domain.entities.quick_match_hole_score import QuickMatchHoleScore
from src.modules.quick_match.domain.exceptions.quick_match_violations import (
    InvalidQuickMatchStatusViolation,
)
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.value_objects.quick_match_hole_score_id import (
    QuickMatchHoleScoreId,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.user.domain.value_objects.user_id import UserId


class SubmitQuickMatchHoleScoreUseCase:
    """
    Registra o actualiza el score propio de un jugador para un hoyo.

    Modelo simple (v1): sin validacion dual jugador/marcador. Cada participante
    solo puede registrar su propio score, y solo mientras la partida esta IN_PROGRESS.
    """

    def __init__(self, uow: QuickMatchUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, request: SubmitHoleScoreRequestDTO) -> HoleScoreResponseDTO:
        player_id = UserId(request.player_user_id)
        quick_match_id = QuickMatchId(request.quick_match_id)

        async with self._uow:
            quick_match = await self._uow.quick_matches.find_by_id(quick_match_id)
            if not quick_match:
                raise QuickMatchNotFoundError(f"Quick match not found: {request.quick_match_id}")

            if not quick_match.is_participant(player_id):
                raise NotQuickMatchParticipantError(
                    "You are not a participant of this quick match."
                )

            if quick_match.status != QuickMatchStatus.IN_PROGRESS:
                raise InvalidQuickMatchStatusViolation(
                    "Scores can only be submitted while the quick match is IN_PROGRESS."
                )

            existing = await self._uow.quick_match_hole_scores.find_by_match_hole_and_player(
                quick_match_id, request.hole_number, player_id
            )

            if existing:
                existing.update_score(request.score)
                await self._uow.quick_match_hole_scores.update(existing)
                hole_score = existing
            else:
                hole_score = QuickMatchHoleScore.create(
                    id=QuickMatchHoleScoreId.generate(),
                    quick_match_id=quick_match_id,
                    hole_number=request.hole_number,
                    player_user_id=player_id,
                    score=request.score,
                )
                await self._uow.quick_match_hole_scores.add(hole_score)

        return HoleScoreResponseDTO(
            hole_number=hole_score.hole_number,
            player_user_id=hole_score.player_user_id.value,
            score=hole_score.score,
        )
