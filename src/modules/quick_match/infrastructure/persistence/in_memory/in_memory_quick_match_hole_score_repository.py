"""In-Memory QuickMatchHoleScore Repository para testing."""

from src.modules.quick_match.domain.entities.quick_match_hole_score import QuickMatchHoleScore
from src.modules.quick_match.domain.repositories.quick_match_hole_score_repository_interface import (
    QuickMatchHoleScoreRepositoryInterface,
)
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_hole_score_id import (
    QuickMatchHoleScoreId,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId


class InMemoryQuickMatchHoleScoreRepository(QuickMatchHoleScoreRepositoryInterface):
    """Implementacion en memoria del repositorio de scores por hoyo para testing."""

    def __init__(self):
        self._hole_scores: dict[QuickMatchHoleScoreId, QuickMatchHoleScore] = {}

    async def add(self, hole_score: QuickMatchHoleScore) -> None:
        self._hole_scores[hole_score.id] = hole_score

    async def update(self, hole_score: QuickMatchHoleScore) -> None:
        if hole_score.id in self._hole_scores:
            self._hole_scores[hole_score.id] = hole_score

    async def find_by_id(self, hole_score_id: QuickMatchHoleScoreId) -> QuickMatchHoleScore | None:
        return self._hole_scores.get(hole_score_id)

    async def find_by_match_hole_and_participant(
        self, quick_match_id: QuickMatchId, hole_number: int, participant_id: ParticipantId
    ) -> QuickMatchHoleScore | None:
        for hs in self._hole_scores.values():
            if (
                hs.quick_match_id == quick_match_id
                and hs.hole_number == hole_number
                and hs.participant_id == participant_id
            ):
                return hs
        return None

    async def find_by_match(self, quick_match_id: QuickMatchId) -> list[QuickMatchHoleScore]:
        results = [hs for hs in self._hole_scores.values() if hs.quick_match_id == quick_match_id]
        results.sort(key=lambda x: x.hole_number)
        return results

    async def find_by_matches(
        self, quick_match_ids: list[QuickMatchId]
    ) -> list[QuickMatchHoleScore]:
        wanted = set(quick_match_ids)
        results = [hs for hs in self._hole_scores.values() if hs.quick_match_id in wanted]
        results.sort(key=lambda x: x.hole_number)
        return results

    async def played_holes(
        self, quick_match_ids: list[QuickMatchId]
    ) -> dict[tuple[QuickMatchId, ParticipantId], int]:
        wanted = set(quick_match_ids)
        jugados: dict[tuple[QuickMatchId, ParticipantId], int] = {}
        for hs in self._hole_scores.values():
            if hs.quick_match_id in wanted:
                clave = (hs.quick_match_id, hs.participant_id)
                jugados[clave] = jugados.get(clave, 0) + 1
        return jugados
