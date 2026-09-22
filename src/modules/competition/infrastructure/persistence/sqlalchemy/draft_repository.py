"""Draft Repository - SQLAlchemy Implementation (FE #653)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.modules.competition.domain.entities.draft import Draft
from src.modules.competition.domain.repositories.draft_repository_interface import (
    DraftRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId


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
