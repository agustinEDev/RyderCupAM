"""In-Memory HoleScore Repository para testing."""

from src.modules.competition.domain.entities.hole_score import HoleScore
from src.modules.competition.domain.repositories.hole_score_repository_interface import (
    HoleScoreRepositoryInterface,
)
from src.modules.competition.domain.value_objects.hole_score_id import HoleScoreId
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.user.domain.value_objects.user_id import UserId


class InMemoryHoleScoreRepository(HoleScoreRepositoryInterface):
    """Implementacion en memoria del repositorio de hole scores para testing."""

    def __init__(self):
        self._scores: dict[HoleScoreId, HoleScore] = {}

    async def add(self, hole_score: HoleScore) -> None:
        self._scores[hole_score.id] = hole_score

    async def add_many(self, hole_scores: list[HoleScore]) -> None:
        for hs in hole_scores:
            self._scores[hs.id] = hs

    async def update(self, hole_score: HoleScore) -> None:
        if hole_score.id in self._scores:
            self._scores[hole_score.id] = hole_score

    async def find_by_match(self, match_id: MatchId) -> list[HoleScore]:
        return [hs for hs in self._scores.values() if hs.match_id == match_id]

    async def find_by_match_and_hole(
        self, match_id: MatchId, hole_number: int
    ) -> list[HoleScore]:
        return [
            hs
            for hs in self._scores.values()
            if hs.match_id == match_id and hs.hole_number == hole_number
        ]

    async def find_one(
        self, match_id: MatchId, hole_number: int, player_user_id: UserId
    ) -> HoleScore | None:
        for hs in self._scores.values():
            if (
                hs.match_id == match_id
                and hs.hole_number == hole_number
                and hs.player_user_id == player_user_id
            ):
                return hs
        return None

    async def find_by_match_and_player(
        self, match_id: MatchId, player_user_id: UserId
    ) -> list[HoleScore]:
        return [
            hs
            for hs in self._scores.values()
            if hs.match_id == match_id and hs.player_user_id == player_user_id
        ]

    async def delete_by_match(self, match_id: MatchId) -> int:
        to_delete = [
            hs_id for hs_id, hs in self._scores.items() if hs.match_id == match_id
        ]
        for hs_id in to_delete:
            del self._scores[hs_id]
        return len(to_delete)
