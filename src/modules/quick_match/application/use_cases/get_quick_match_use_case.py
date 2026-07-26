"""Caso de Uso: Obtener el detalle de una Partida Rapida (con scores y standing)."""

from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.quick_match.application.dto.quick_match_dto import (
    HoleScoreResponseDTO,
    QuickMatchDetailResponseDTO,
    QuickMatchStandingResponseDTO,
)
from src.modules.quick_match.application.exceptions import (
    NotQuickMatchParticipantError,
    QuickMatchNotFoundError,
)
from src.modules.quick_match.application.mappers.quick_match_mapper import QuickMatchDTOMapper
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

TOTAL_HOLES = 18


class GetQuickMatchUseCase:
    """Obtiene el detalle de una partida rapida: datos, scores y standing calculado."""

    def __init__(self, uow: QuickMatchUnitOfWorkInterface, user_uow: UserUnitOfWorkInterface):
        self._uow = uow
        self._user_uow = user_uow
        self._scoring_service = ScoringService()

    async def execute(
        self, quick_match_id_raw: str, current_user_id_raw: str
    ) -> QuickMatchDetailResponseDTO:
        current_user_id = UserId(current_user_id_raw)

        async with self._uow:
            quick_match = await self._uow.quick_matches.find_by_id(
                QuickMatchId(quick_match_id_raw)
            )
            if not quick_match:
                raise QuickMatchNotFoundError(f"Quick match not found: {quick_match_id_raw}")

            if not quick_match.is_participant(current_user_id):
                raise NotQuickMatchParticipantError(
                    "You are not a participant of this quick match."
                )

            hole_scores = await self._uow.quick_match_hole_scores.find_by_match(quick_match.id)

        base_dto = await QuickMatchDTOMapper.to_response_dto(quick_match, self._user_uow)

        hole_scores_dto = [
            HoleScoreResponseDTO(
                hole_number=hs.hole_number,
                player_user_id=hs.player_user_id.value,
                score=hs.score,
            )
            for hs in sorted(hole_scores, key=lambda h: h.hole_number)
        ]

        standing_dto = self._compute_standing(quick_match, hole_scores)

        return QuickMatchDetailResponseDTO(
            **base_dto.model_dump(),
            hole_scores=hole_scores_dto,
            standing=standing_dto,
        )

    def _compute_standing(self, quick_match, hole_scores) -> QuickMatchStandingResponseDTO | None:
        participants = quick_match.participants
        if len(participants) < 2:  # noqa: PLR2004
            return None

        team_a_ids = {p.user_id for p in participants if (p.team or "A") == "A"}
        team_b_ids = {p.user_id for p in participants if p.team == "B"}
        if not team_b_ids and len(participants) == 2:  # noqa: PLR2004 - SINGLES: no team field
            team_a_ids = {participants[0].user_id}
            team_b_ids = {participants[1].user_id}

        scores_by_hole: dict[int, dict] = {}
        for hs in hole_scores:
            scores_by_hole.setdefault(hs.hole_number, {})[hs.player_user_id] = hs.score

        hole_results = []
        for hole_number in range(1, TOTAL_HOLES + 1):
            scores = scores_by_hole.get(hole_number)
            if not scores:
                continue
            if not all(uid in scores for uid in team_a_ids | team_b_ids):
                continue

            team_a_scores = [scores[uid] for uid in team_a_ids]
            team_b_scores = [scores[uid] for uid in team_b_ids]
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
