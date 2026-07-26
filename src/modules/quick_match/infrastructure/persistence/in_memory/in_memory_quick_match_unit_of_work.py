"""In-Memory QuickMatch Unit of Work para testing."""

from src.modules.quick_match.domain.repositories.quick_match_hole_score_repository_interface import (
    QuickMatchHoleScoreRepositoryInterface,
)
from src.modules.quick_match.domain.repositories.quick_match_repository_interface import (
    QuickMatchRepositoryInterface,
)
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.infrastructure.persistence.in_memory.in_memory_quick_match_hole_score_repository import (
    InMemoryQuickMatchHoleScoreRepository,
)
from src.modules.quick_match.infrastructure.persistence.in_memory.in_memory_quick_match_repository import (
    InMemoryQuickMatchRepository,
)


class InMemoryQuickMatchUnitOfWork(QuickMatchUnitOfWorkInterface):
    """Implementacion en memoria de la Unit of Work del modulo QuickMatch para testing."""

    def __init__(self):
        self._quick_matches = InMemoryQuickMatchRepository()
        self._quick_match_hole_scores = InMemoryQuickMatchHoleScoreRepository()
        self.committed = False

    @property
    def quick_matches(self) -> QuickMatchRepositoryInterface:
        return self._quick_matches

    @property
    def quick_match_hole_scores(self) -> QuickMatchHoleScoreRepositoryInterface:
        return self._quick_match_hole_scores

    async def __aenter__(self):
        self.committed = False
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.rollback()
        else:
            try:
                await self.commit()
            except Exception:
                await self.rollback()
                raise

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.committed = False

    async def flush(self) -> None:
        pass

    def is_active(self) -> bool:
        return True
