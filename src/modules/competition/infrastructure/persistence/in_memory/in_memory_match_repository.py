"""In-Memory Match Repository para testing."""

from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.repositories.match_repository_interface import (
    MatchRepositoryInterface,
)
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.round_id import RoundId


class InMemoryMatchRepository(MatchRepositoryInterface):
    """Implementacion en memoria del repositorio de partidos para testing."""

    def __init__(self):
        self._matches: dict[MatchId, Match] = {}

    async def add(self, match: Match) -> None:
        self._matches[match.id] = match

    async def update(self, match: Match) -> None:
        if match.id in self._matches:
            self._matches[match.id] = match

    async def find_by_id(self, match_id: MatchId) -> Match | None:
        return self._matches.get(match_id)

    async def find_by_round(self, round_id: RoundId) -> list[Match]:
        return [m for m in self._matches.values() if m.round_id == round_id]

    async def delete(self, match_id: MatchId) -> bool:
        if match_id in self._matches:
            del self._matches[match_id]
            return True
        return False
