"""Las plazas en franjas, en Postgres (#251)."""

import uuid
from datetime import datetime

from sqlalchemy import delete, select, update
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
                from_waiting_list_at=plaza.desde_espera,
                acknowledged_at=plaza.vista,
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
        return await self._donde(tee_window_places_table.c.competition_id == competition_id)

    async def de_la_franja(self, round_id: RoundId) -> list[PlazaEnFranja]:
        return await self._donde(tee_window_places_table.c.round_id == round_id)

    async def _donde(self, condicion) -> list[PlazaEnFranja]:
        tabla = tee_window_places_table
        result = await self._session.execute(
            select(tabla).where(condicion).order_by(tabla.c.created_at, tabla.c.id)
        )
        return [
            PlazaEnFranja(
                id=uuid.UUID(fila.id),
                competition_id=fila.competition_id,
                round_id=fila.round_id,
                user_id=fila.user_id,
                creada=fila.created_at,
                desde_espera=fila.from_waiting_list_at,
                vista=fila.acknowledged_at,
            )
            for fila in result
        ]

    async def asignadas_sin_ver(self, user_id: UserId) -> list[PlazaEnFranja]:
        tabla = tee_window_places_table
        return await self._donde(
            (tabla.c.user_id == user_id)
            & tabla.c.from_waiting_list_at.is_not(None)
            & tabla.c.acknowledged_at.is_(None)
        )

    async def marcar_vista(self, round_id: RoundId, user_id: UserId, momento: datetime) -> None:
        tabla = tee_window_places_table
        await self._session.execute(
            update(tabla)
            .where(tabla.c.round_id == round_id, tabla.c.user_id == user_id)
            .values(acknowledged_at=momento)
        )
