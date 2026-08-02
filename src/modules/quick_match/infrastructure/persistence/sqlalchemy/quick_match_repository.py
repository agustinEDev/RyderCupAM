"""QuickMatch Repository - SQLAlchemy Implementation."""

from sqlalchemy import and_, cast, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

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
        # QuickMatchParticipant.__eq__ compares only participant_id (by domain design,
        # for stable identity across list ops) — so SQLAlchemy's default dirty-check
        # on the `participants` JSONB column (list equality via `==`) can't see a
        # same-length list where only e.g. custom_handicap changed on one entry, and
        # silently skips writing it. Force it into every UPDATE regardless.
        flag_modified(quick_match, "_participants")

    async def find_by_id(self, quick_match_id: QuickMatchId) -> QuickMatch | None:
        return await self._session.get(QuickMatch, quick_match_id)

    async def find_by_id_for_update(self, quick_match_id: QuickMatchId) -> QuickMatch | None:
        return await self._session.get(
            QuickMatch, quick_match_id, with_for_update=True, populate_existing=True
        )

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

    async def count_all(self) -> int:
        """Cuenta el total de partidas rapidas en el sistema."""
        stmt = select(func.count()).select_from(QuickMatch)
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def exists_created_by(self, creator_id: UserId) -> bool:
        """True si el usuario ha creado alguna partida rapida."""
        stmt = (
            select(func.count())
            .select_from(QuickMatch)
            .where(QuickMatch._creator_id == creator_id)
        )
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0
