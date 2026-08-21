"""Caso de Uso: Registrar por delegacion el score de otro participante."""

from src.modules.quick_match.application.dto.quick_match_dto import (
    HoleScoreResponseDTO,
    SubmitProxyHoleScoreRequestDTO,
)
from src.modules.quick_match.application.exceptions import (
    NotAScorerError,
    QuickMatchNotFoundError,
    TargetParticipantNotFoundError,
)
from src.modules.quick_match.domain.entities.quick_match_hole_score import QuickMatchHoleScore
from src.modules.quick_match.domain.exceptions.quick_match_violations import (
    InvalidHoleScoreViolation,
    InvalidQuickMatchStatusViolation,
    NotAssignedScorerViolation,
)
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.services.scoring_coverage_service import (
    ScoringCoverageService,
)
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_hole_score_id import (
    QuickMatchHoleScoreId,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.user.domain.value_objects.user_id import UserId


class SubmitProxyHoleScoreUseCase:
    """
    Registra el score de un hoyo en nombre de otro participante (invitado o
    registrado no seleccionado como anotador).

    Solo puede hacerlo el anotador al que ese participante le fue asignado
    (segun el reparto calculado por ScoringCoverageService).
    """

    def __init__(
        self, uow: QuickMatchUnitOfWorkInterface, coverage_service: ScoringCoverageService
    ):
        self._uow = uow
        self._coverage_service = coverage_service

    async def execute(self, request: SubmitProxyHoleScoreRequestDTO) -> HoleScoreResponseDTO:
        scorer_id = UserId(request.scorer_user_id)
        scorer_participant_id = ParticipantId(scorer_id.value)
        target_participant_id = ParticipantId(request.target_participant_id)
        quick_match_id = QuickMatchId(request.quick_match_id)

        async with self._uow:
            quick_match = await self._uow.quick_matches.find_by_id(quick_match_id)
            if not quick_match:
                raise QuickMatchNotFoundError(f"Quick match not found: {request.quick_match_id}")

            if quick_match.status != QuickMatchStatus.IN_PROGRESS:
                raise InvalidQuickMatchStatusViolation(
                    "Scores can only be submitted while the quick match is IN_PROGRESS."
                )

            if not quick_match.is_scorer(scorer_participant_id):
                raise NotAScorerError("Only a configured scorer can record scores by proxy.")

            if not quick_match.is_participant(target_participant_id):
                raise TargetParticipantNotFoundError(
                    f"{target_participant_id} is not a participant of this quick match."
                )

            assignments = self._coverage_service.compute_assignments(
                participants=quick_match.participants,
                scorer_ids=quick_match.scorer_ids,
                creator_participant_id=quick_match.creator_participant_id,
                match_format=quick_match.match_format,
            )
            if target_participant_id not in assignments.get(scorer_participant_id, []):
                raise NotAssignedScorerViolation(
                    f"{target_participant_id} is not assigned to this scorer."
                )

            if request.score is None and not quick_match.allows_picked_up_holes():
                raise InvalidHoleScoreViolation(
                    "A picked-up hole cannot be recorded in a Medal match: "
                    "stroke play requires holing out on every hole."
                )

            existing = await self._uow.quick_match_hole_scores.find_by_match_hole_and_participant(
                quick_match_id, request.hole_number, target_participant_id
            )

            if existing:
                existing.update_score(
                    request.score, recorded_by_participant_id=scorer_participant_id
                )
                await self._uow.quick_match_hole_scores.update(existing)
                hole_score = existing
            else:
                hole_score = QuickMatchHoleScore.create(
                    id=QuickMatchHoleScoreId.generate(),
                    quick_match_id=quick_match_id,
                    hole_number=request.hole_number,
                    participant_id=target_participant_id,
                    score=request.score,
                    recorded_by_participant_id=scorer_participant_id,
                )
                await self._uow.quick_match_hole_scores.add(hole_score)

        return HoleScoreResponseDTO(
            hole_number=hole_score.hole_number,
            participant_id=hole_score.participant_id.value,
            score=hole_score.score,
            recorded_by_participant_id=hole_score.recorded_by_participant_id.value,
        )
