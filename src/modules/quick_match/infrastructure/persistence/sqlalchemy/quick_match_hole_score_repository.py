"""QuickMatchHoleScore Repository - SQLAlchemy Implementation."""

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.quick_match.domain.entities.quick_match_hole_score import QuickMatchHoleScore
from src.modules.quick_match.domain.repositories.quick_match_hole_score_repository_interface import (
    QuickMatchHoleScoreRepositoryInterface,
)
from src.modules.quick_match.domain.value_objects.quick_match_hole_score_id import (
    QuickMatchHoleScoreId,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.user.domain.value_objects.user_id import UserId


class SQLAlchemyQuickMatchHoleScoreRepository(QuickMatchHoleScoreRepositoryInterface):
    """Implementacion asincrona del repositorio de scores por hoyo con SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, hole_score: QuickMatchHoleScore) -> None:
        self._session.add(hole_score)

    async def update(self, hole_score: QuickMatchHoleScore) -> None:
        self._session.add(hole_score)

    async def find_by_id(
        self, hole_score_id: QuickMatchHoleScoreId
    ) -> QuickMatchHoleScore | None:
        return await self._session.get(QuickMatchHoleScore, hole_score_id)

    async def find_by_match_hole_and_player(
        self, quick_match_id: QuickMatchId, hole_number: int, player_user_id: UserId
    ) -> QuickMatchHoleScore | None:
        stmt = select(QuickMatchHoleScore).where(
            and_(
                QuickMatchHoleScore._quick_match_id == quick_match_id,
                QuickMatchHoleScore._hole_number == hole_number,
                QuickMatchHoleScore._player_user_id == player_user_id,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def find_by_match(self, quick_match_id: QuickMatchId) -> list[QuickMatchHoleScore]:
        stmt = (
            select(QuickMatchHoleScore)
            .where(QuickMatchHoleScore._quick_match_id == quick_match_id)
            .order_by(QuickMatchHoleScore._hole_number.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
