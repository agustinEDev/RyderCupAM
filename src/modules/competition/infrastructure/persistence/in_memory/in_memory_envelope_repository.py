"""Envelope Repository - Implementacion en memoria para tests (FE #655)."""

from src.modules.competition.domain.entities.envelope import Envelope
from src.modules.competition.domain.repositories.envelope_repository_interface import (
    EnvelopeRepositoryInterface,
)
from src.modules.competition.domain.value_objects.round_id import RoundId


class InMemoryEnvelopeRepository(EnvelopeRepositoryInterface):
    """Repositorio de sobres en memoria."""

    def __init__(self):
        self._envelopes: dict[tuple[str, str], Envelope] = {}

    async def add(self, envelope: Envelope) -> None:
        self._envelopes[(str(envelope.round_id.value), envelope.team)] = envelope

    async def update(self, envelope: Envelope) -> None:
        self._envelopes[(str(envelope.round_id.value), envelope.team)] = envelope

    async def find_by_round_and_team(self, round_id: RoundId, team: str) -> Envelope | None:
        return self._envelopes.get((str(round_id.value), team))

    async def find_by_round(self, round_id: RoundId) -> list[Envelope]:
        return [e for e in self._envelopes.values() if e.round_id == round_id]

    async def find_by_round_and_team_for_update(
        self, round_id: RoundId, team: str
    ) -> Envelope | None:
        return await self.find_by_round_and_team(round_id, team)
