"""QuickMatch Unit of Work - SQLAlchemy Implementation."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.quick_match.domain.repositories.quick_match_hole_score_repository_interface import (
    QuickMatchHoleScoreRepositoryInterface,
)
from src.modules.quick_match.domain.repositories.quick_match_repository_interface import (
    QuickMatchRepositoryInterface,
)
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.infrastructure.persistence.sqlalchemy.quick_match_hole_score_repository import (
    SQLAlchemyQuickMatchHoleScoreRepository,
)
from src.modules.quick_match.infrastructure.persistence.sqlalchemy.quick_match_repository import (
    SQLAlchemyQuickMatchRepository,
)


class SQLAlchemyQuickMatchUnitOfWork(QuickMatchUnitOfWorkInterface):
    """Implementacion asincrona de la Unit of Work del modulo QuickMatch con SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._quick_matches = SQLAlchemyQuickMatchRepository(session)
        self._quick_match_hole_scores = SQLAlchemyQuickMatchHoleScoreRepository(session)

    @property
    def quick_matches(self) -> QuickMatchRepositoryInterface:
        return self._quick_matches

    @property
    def quick_match_hole_scores(self) -> QuickMatchHoleScoreRepositoryInterface:
        return self._quick_match_hole_scores

    async def __aenter__(self):
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
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def flush(self) -> None:
        await self._session.flush()

    def is_active(self) -> bool:
        return self._session.is_active
