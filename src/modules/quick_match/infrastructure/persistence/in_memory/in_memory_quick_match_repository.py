"""In-Memory QuickMatch Repository para testing."""

from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.repositories.quick_match_repository_interface import (
    QuickMatchRepositoryInterface,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.user.domain.value_objects.user_id import UserId


class InMemoryQuickMatchRepository(QuickMatchRepositoryInterface):
    """Implementacion en memoria del repositorio de partidas rapidas para testing."""

    def __init__(self):
        self._quick_matches: dict[QuickMatchId, QuickMatch] = {}

    async def add(self, quick_match: QuickMatch) -> None:
        self._quick_matches[quick_match.id] = quick_match

    async def update(self, quick_match: QuickMatch) -> None:
        if quick_match.id in self._quick_matches:
            self._quick_matches[quick_match.id] = quick_match

    async def find_by_id(self, quick_match_id: QuickMatchId) -> QuickMatch | None:
        return self._quick_matches.get(quick_match_id)

    async def list_for_user(
        self,
        user_id: UserId,
        status: QuickMatchStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[QuickMatch]:
        results = [
            qm
            for qm in self._quick_matches.values()
            if qm.is_participant(user_id) and (status is None or qm.status == status)
        ]
        results.sort(key=lambda x: x.created_at, reverse=True)
        return results[offset : offset + limit]

    async def count_for_user(
        self, user_id: UserId, status: QuickMatchStatus | None = None
    ) -> int:
        return sum(
            1
            for qm in self._quick_matches.values()
            if qm.is_participant(user_id) and (status is None or qm.status == status)
        )
