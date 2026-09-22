"""Draft Repository - Implementacion en memoria para tests (FE #653)."""

from src.modules.competition.domain.entities.draft import Draft
from src.modules.competition.domain.repositories.draft_repository_interface import (
    DraftRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId


class InMemoryDraftRepository(DraftRepositoryInterface):
    """Salas de draft en memoria."""

    def __init__(self):
        self._drafts: dict[str, Draft] = {}

    async def add(self, draft: Draft) -> None:
        self._drafts[str(draft.competition_id.value)] = draft

    async def update(self, draft: Draft) -> None:
        self._drafts[str(draft.competition_id.value)] = draft

    async def find_by_competition(self, competition_id: CompetitionId) -> Draft | None:
        return self._drafts.get(str(competition_id.value))

    async def find_by_competition_for_update(
        self, competition_id: CompetitionId
    ) -> Draft | None:
        # En memoria no hay nada que bloquear. Sin pasar por `find_by_competition`:
        # los tests espian cual de las dos lecturas usa cada camino
        return self._drafts.get(str(competition_id.value))
