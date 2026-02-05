"""Round Repository - SQLAlchemy Implementation."""

from datetime import date

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.round_repository_interface import (
    RoundRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.round_id import RoundId


class SQLAlchemyRoundRepository(RoundRepositoryInterface):
    """Implementacion asincrona del repositorio de rondas con SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, round: Round) -> None:
        self._session.add(round)

    async def update(self, round: Round) -> None:
        self._session.add(round)

    async def find_by_id(self, round_id: RoundId) -> Round | None:
        return await self._session.get(Round, round_id)

    async def find_by_competition(
        self, competition_id: CompetitionId
    ) -> list[Round]:
        statement = (
            select(Round)
            .where(Round._competition_id == competition_id)
            .order_by(Round._round_date.asc(), Round._created_at.asc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def find_by_competition_and_date(
        self, competition_id: CompetitionId, round_date: date
    ) -> list[Round]:
        statement = (
            select(Round)
            .where(
                and_(
                    Round._competition_id == competition_id,
                    Round._round_date == round_date,
                )
            )
            .order_by(Round._created_at.asc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def delete(self, round_id: RoundId) -> bool:
        round = await self.find_by_id(round_id)
        if round is None:
            return False
        await self._session.delete(round)
        return True
