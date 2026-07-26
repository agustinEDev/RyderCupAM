"""QuickMatch Repository - SQLAlchemy Implementation."""

from sqlalchemy import and_, cast, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.repositories.quick_match_repository_interface import (
    QuickMatchRepositoryInterface,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.quick_match.infrastructure.persistence.mappers.quick_match_mapper import (
    quick_matches_table,
)
from src.modules.user.domain.value_objects.user_id import UserId


class SQLAlchemyQuickMatchRepository(QuickMatchRepositoryInterface):
    """Implementacion asincrona del repositorio de partidas rapidas con SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, quick_match: QuickMatch) -> None:
        self._session.add(quick_match)

    async def update(self, quick_match: QuickMatch) -> None:
        self._session.add(quick_match)

    async def find_by_id(self, quick_match_id: QuickMatchId) -> QuickMatch | None:
        return await self._session.get(QuickMatch, quick_match_id)

    def _participant_filter(self, user_id: UserId):
        return quick_matches_table.c.participants.op("@>")(
            cast([{"user_id": str(user_id.value)}], JSONB)
        )

    async def list_for_user(
        self,
        user_id: UserId,
        status: QuickMatchStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[QuickMatch]:
        conditions = [self._participant_filter(user_id)]
        if status is not None:
            conditions.append(QuickMatch._status == status)

        stmt = (
            select(QuickMatch)
            .where(and_(*conditions))
            .order_by(QuickMatch._created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_user(
        self, user_id: UserId, status: QuickMatchStatus | None = None
    ) -> int:
        conditions = [self._participant_filter(user_id)]
        if status is not None:
            conditions.append(QuickMatch._status == status)

        stmt = select(func.count()).select_from(QuickMatch).where(and_(*conditions))
        result = await self._session.execute(stmt)
        return result.scalar() or 0
