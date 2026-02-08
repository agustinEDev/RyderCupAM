"""Match Repository - SQLAlchemy Implementation."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.repositories.match_repository_interface import (
    MatchRepositoryInterface,
)
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.round_id import RoundId


class SQLAlchemyMatchRepository(MatchRepositoryInterface):
    """Implementacion asincrona del repositorio de partidos con SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, match: Match) -> None:
        self._session.add(match)

    async def update(self, match: Match) -> None:
        self._session.add(match)

    async def find_by_id(self, match_id: MatchId) -> Match | None:
        return await self._session.get(Match, match_id)

    async def find_by_round(self, round_id: RoundId) -> list[Match]:
        statement = (
            select(Match).where(Match._round_id == round_id).order_by(Match._match_number.asc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def delete(self, match_id: MatchId) -> bool:
        match = await self.find_by_id(match_id)
        if match is None:
            return False
        await self._session.delete(match)
        return True
