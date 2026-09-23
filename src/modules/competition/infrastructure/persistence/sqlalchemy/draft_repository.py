"""Draft Repository - SQLAlchemy Implementation (FE #653)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.modules.competition.domain.entities.draft import Draft
from src.modules.competition.domain.repositories.draft_repository_interface import (
    DraftRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId


class SQLAlchemyDraftRepository(DraftRepositoryInterface):
    """Implementacion asincrona del repositorio de salas de draft."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, draft: Draft) -> None:
        self._session.add(draft)

    async def update(self, draft: Draft) -> None:
        self._session.add(draft)

    async def find_by_competition(self, competition_id: CompetitionId) -> Draft | None:
        statement = select(Draft).where(Draft._competition_id == competition_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def find_by_competition_for_update(self, competition_id: CompetitionId) -> Draft | None:
        # `populate_existing`, como en el resto de lecturas bloqueantes: sin el,
        # una sala ya cargada vuelve con el estado de antes del bloqueo y dos
        # peticiones simultaneas eligen dos veces por el mismo turno
        statement = (
            select(Draft)
            .where(Draft._competition_id == competition_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def exists_by_captain(self, user_id: UserId) -> bool:
        statement = (
            select(Draft.__table__.c.id)
            .where((Draft._team_a_captain_id == user_id) | (Draft._team_b_captain_id == user_id))
            .limit(1)
        )
        result = await self._session.execute(statement)
        return result.first() is not None
