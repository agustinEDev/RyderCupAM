"""Caso de Uso: Obtener el detalle de una Partida Rapida (con scores y standing)."""

from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.quick_match.application.dto.quick_match_dto import (
    HoleScoreResponseDTO,
    QuickMatchDetailResponseDTO,
    QuickMatchStandingResponseDTO,
    ScoringAssignmentDTO,
)
from src.modules.quick_match.application.exceptions import (
    NotQuickMatchParticipantError,
    QuickMatchNotFoundError,
)
from src.modules.quick_match.application.mappers.quick_match_mapper import QuickMatchDTOMapper
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.services.scoring_coverage_service import (
    ScoringCoverageService,
)
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

TOTAL_HOLES = 18


class GetQuickMatchUseCase:
    """Obtiene el detalle de una partida rapida: datos, scores, standing y reparto de anotacion."""

    def __init__(self, uow: QuickMatchUnitOfWorkInterface, user_uow: UserUnitOfWorkInterface):
        self._uow = uow
        self._user_uow = user_uow
        self._scoring_service = ScoringService()
        self._coverage_service = ScoringCoverageService()

    async def execute(
        self, quick_match_id_raw: str, current_user_id_raw: str
    ) -> QuickMatchDetailResponseDTO:
        current_participant_id = ParticipantId(UserId(current_user_id_raw).value)

        async with self._uow:
            quick_match = await self._uow.quick_matches.find_by_id(QuickMatchId(quick_match_id_raw))
            if not quick_match:
                raise QuickMatchNotFoundError(f"Quick match not found: {quick_match_id_raw}")

            if not quick_match.is_participant(current_participant_id):
                raise NotQuickMatchParticipantError(
                    "You are not a participant of this quick match."
                )

            hole_scores = await self._uow.quick_match_hole_scores.find_by_match(quick_match.id)

        registered_ids = [p.user_id for p in quick_match.participants if p.user_id is not None]
        async with self._user_uow:
            users_by_id = {}
            for user_id in registered_ids:
                user = await self._user_uow.users.find_by_id(user_id)
                if user:
                    users_by_id[user_id] = user

        base_dto = await QuickMatchDTOMapper.to_response_dto(
            quick_match, self._user_uow, users_by_id=users_by_id
        )

        hole_scores_dto = [
            HoleScoreResponseDTO(
                hole_number=hs.hole_number,
                participant_id=hs.participant_id.value,
                score=hs.score,
                recorded_by_participant_id=hs.recorded_by_participant_id.value,
            )
            for hs in sorted(hole_scores, key=lambda h: h.hole_number)
        ]

        standing_dto = self._compute_standing(quick_match, hole_scores)
        assignments_dto = self._build_assignments(quick_match, users_by_id)

        return QuickMatchDetailResponseDTO(
            **base_dto.model_dump(),
            hole_scores=hole_scores_dto,
            standing=standing_dto,
            scoring_assignments=assignments_dto,
        )

    def _build_assignments(self, quick_match, users_by_id) -> list[ScoringAssignmentDTO]:
        if not quick_match.scorer_ids:
            return []

        assignments = self._coverage_service.compute_assignments(
            participants=quick_match.participants,
            scorer_ids=quick_match.scorer_ids,
            creator_participant_id=quick_match.creator_participant_id,
        )

        result = []
        for scorer_id, covered_ids in assignments.items():
            scorer = quick_match.find_participant(scorer_id)
            user = users_by_id.get(scorer.user_id) if scorer else None
            scorer_name = f"{user.first_name} {user.last_name}" if user else "Unknown"
            result.append(
                ScoringAssignmentDTO(
                    scorer_participant_id=scorer_id.value,
                    scorer_name=scorer_name,
                    covered_participant_ids=[cid.value for cid in covered_ids],
                )
            )
        return result

    def _compute_standing(self, quick_match, hole_scores) -> QuickMatchStandingResponseDTO | None:
        if quick_match.match_format is None:
            # Partido libre (MEDAL/STABLEFORD): sin equipos, no hay standing A-vs-B.
            # La clasificacion individual se calcula en el frontend a partir de hole_scores.
            return None

        rosters = quick_match.team_rosters()
        if rosters is None:
            return None
        team_a_ids, team_b_ids = rosters

        scores_by_hole: dict[int, dict] = {}
        for hs in hole_scores:
            scores_by_hole.setdefault(hs.hole_number, {})[hs.participant_id] = hs.score

        hole_results = []
        for hole_number in range(1, TOTAL_HOLES + 1):
            scores = scores_by_hole.get(hole_number)
            if not scores:
                continue
            if not all(pid in scores for pid in team_a_ids | team_b_ids):
                continue

            team_a_scores = [scores[pid] for pid in team_a_ids]
            team_b_scores = [scores[pid] for pid in team_b_ids]
            hole_results.append(
                self._scoring_service.calculate_hole_winner(
                    team_a_scores, team_b_scores, quick_match.match_format
                )
            )

        if not hole_results:
            return None

        standing = self._scoring_service.calculate_match_standing(hole_results)
        return QuickMatchStandingResponseDTO(
            status=standing["status"],
            leading_team=standing["leading_team"],
            holes_played=standing["holes_played"],
            holes_remaining=standing["holes_remaining"],
            is_decided=self._scoring_service.is_match_decided(standing),
        )
