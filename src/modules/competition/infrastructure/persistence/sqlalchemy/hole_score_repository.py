"""HoleScore Repository - SQLAlchemy Implementation."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.modules.competition.domain.entities.hole_score import HoleScore
from src.modules.competition.domain.repositories.hole_score_repository_interface import (
    HoleScoreRepositoryInterface,
)
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.user.domain.value_objects.user_id import UserId


class SQLAlchemyHoleScoreRepository(HoleScoreRepositoryInterface):
    """Implementacion asincrona del repositorio de hole scores con SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, hole_score: HoleScore) -> None:
        self._session.add(hole_score)

    async def add_many(self, hole_scores: list[HoleScore]) -> None:
        self._session.add_all(hole_scores)

    async def update(self, hole_score: HoleScore) -> None:
        self._session.add(hole_score)

    async def find_by_match(self, match_id: MatchId) -> list[HoleScore]:
        statement = (
            select(HoleScore)
            .where(HoleScore._match_id == match_id)
            .order_by(HoleScore._hole_number.asc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def find_by_match_and_hole(
        self, match_id: MatchId, hole_number: int
    ) -> list[HoleScore]:
        statement = select(HoleScore).where(
            HoleScore._match_id == match_id,
            HoleScore._hole_number == hole_number,
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def find_one(
        self, match_id: MatchId, hole_number: int, player_user_id: UserId
    ) -> HoleScore | None:
        statement = select(HoleScore).where(
            HoleScore._match_id == match_id,
            HoleScore._hole_number == hole_number,
            HoleScore._player_user_id == player_user_id,
        )
        result = await self._session.execute(statement)
        return result.scalars().first()

    async def find_by_match_and_player(
        self, match_id: MatchId, player_user_id: UserId
    ) -> list[HoleScore]:
        statement = (
            select(HoleScore)
            .where(
                HoleScore._match_id == match_id,
                HoleScore._player_user_id == player_user_id,
            )
            .order_by(HoleScore._hole_number.asc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def delete_by_match(self, match_id: MatchId) -> int:
        statement = delete(HoleScore).where(HoleScore._match_id == match_id)
        result = await self._session.execute(statement)
        return result.rowcount
