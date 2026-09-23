"""Envelope Repository - SQLAlchemy Implementation (FE #655)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.modules.competition.domain.entities.envelope import Envelope
from src.modules.competition.domain.repositories.envelope_repository_interface import (
    EnvelopeRepositoryInterface,
)
from src.modules.competition.domain.value_objects.round_id import RoundId


class SQLAlchemyEnvelopeRepository(EnvelopeRepositoryInterface):
    """Implementacion asincrona del repositorio de sobres."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, envelope: Envelope) -> None:
        self._session.add(envelope)

    async def update(self, envelope: Envelope) -> None:
        # La sesion ya sigue al objeto: el flush del Unit of Work lo escribe
        self._session.add(envelope)

    async def find_by_round_and_team(self, round_id: RoundId, team: str) -> Envelope | None:
        statement = select(Envelope).where(Envelope._round_id == round_id, Envelope._team == team)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def find_by_round(self, round_id: RoundId) -> list[Envelope]:
        statement = select(Envelope).where(Envelope._round_id == round_id)
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def delete_by_round(self, round_id: RoundId) -> int:
        sobres = await self.find_by_round(round_id)
        for sobre in sobres:
            await self._session.delete(sobre)
        return len(sobres)

    async def find_by_round_and_team_for_update(
        self, round_id: RoundId, team: str
    ) -> Envelope | None:
        statement = (
            select(Envelope)
            .where(Envelope._round_id == round_id, Envelope._team == team)
            .with_for_update()
            # `populate_existing`: sin esto SQLAlchemy devuelve el objeto que ya
            # tenia en la sesion y la fila bloqueada se lee para nada
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()
