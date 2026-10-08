"""Las plazas en franjas, en Postgres (#251)."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.competition.domain.entities.plaza_en_franja import PlazaEnFranja
from src.modules.competition.domain.repositories.plaza_en_franja_repository_interface import (
    PlazaEnFranjaRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.infrastructure.persistence.sqlalchemy.mappers import (
    tee_window_places_table,
)
from src.modules.user.domain.value_objects.user_id import UserId


class SQLAlchemyPlazaEnFranjaRepository(PlazaEnFranjaRepositoryInterface):
    """Una fila por jugador y franja (única)."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, plaza: PlazaEnFranja) -> None:
        await self._session.execute(
            tee_window_places_table.insert().values(
                id=str(plaza.id),
                competition_id=plaza.competition_id,
                round_id=plaza.round_id,
                user_id=plaza.user_id,
                created_at=plaza.creada,
            )
        )

    async def quitar(self, round_id: RoundId, user_id: UserId) -> None:
        tabla = tee_window_places_table
        await self._session.execute(
            delete(tabla).where(tabla.c.round_id == round_id, tabla.c.user_id == user_id)
        )

    async def quitar_del_jugador(self, competition_id: CompetitionId, user_id: UserId) -> None:
        tabla = tee_window_places_table
        await self._session.execute(
            delete(tabla).where(
                tabla.c.competition_id == competition_id, tabla.c.user_id == user_id
            )
        )

    async def de_la_competicion(self, competition_id: CompetitionId) -> list[PlazaEnFranja]:
        tabla = tee_window_places_table
        result = await self._session.execute(
            select(tabla)
            .where(tabla.c.competition_id == competition_id)
            .order_by(tabla.c.created_at, tabla.c.id)
        )
        return [
            PlazaEnFranja(
                id=uuid.UUID(fila.id),
                competition_id=fila.competition_id,
                round_id=fila.round_id,
                user_id=fila.user_id,
                creada=fila.created_at,
            )
            for fila in result
        ]
