"""In-Memory Round Repository para testing."""

from datetime import date

from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.round_repository_interface import (
    RoundRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.round_id import RoundId


class InMemoryRoundRepository(RoundRepositoryInterface):
    """Implementacion en memoria del repositorio de rondas para testing."""

    def __init__(self):
        self._rounds: dict[RoundId, Round] = {}

    async def add(self, round: Round) -> None:
        self._rounds[round.id] = round

    async def update(self, round: Round) -> None:
        if round.id in self._rounds:
            self._rounds[round.id] = round

    async def find_by_id(self, round_id: RoundId) -> Round | None:
        return self._rounds.get(round_id)

    async def find_by_competition(
        self, competition_id: CompetitionId
    ) -> list[Round]:
        return [
            r
            for r in self._rounds.values()
            if r.competition_id == competition_id
        ]

    async def find_by_competition_and_date(
        self, competition_id: CompetitionId, round_date: date
    ) -> list[Round]:
        return [
            r
            for r in self._rounds.values()
            if r.competition_id == competition_id and r.round_date == round_date
        ]

    async def delete(self, round_id: RoundId) -> bool:
        if round_id in self._rounds:
            del self._rounds[round_id]
            return True
        return False
