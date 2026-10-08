"""Las listas de espera, en Postgres (#251)."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.competition.domain.entities.espera_en_franja import EsperaEnFranja
from src.modules.competition.domain.repositories.espera_en_franja_repository_interface import (
    EsperaEnFranjaRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.infrastructure.persistence.sqlalchemy.mappers import (
    tee_window_waits_table,
)
from src.modules.user.domain.value_objects.user_id import UserId


class SQLAlchemyEsperaEnFranjaRepository(EsperaEnFranjaRepositoryInterface):
    """Una fila por jugador y franja (única), ordenadas por llegada."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, espera: EsperaEnFranja) -> None:
        await self._session.execute(
            tee_window_waits_table.insert().values(
                id=str(espera.id),
                competition_id=espera.competition_id,
                round_id=espera.round_id,
                user_id=espera.user_id,
                created_at=espera.creada,
            )
        )

    async def quitar(self, round_id: RoundId, user_id: UserId) -> None:
        tabla = tee_window_waits_table
        await self._session.execute(
            delete(tabla).where(tabla.c.round_id == round_id, tabla.c.user_id == user_id)
        )

    async def de_la_competicion(self, competition_id: CompetitionId) -> list[EsperaEnFranja]:
        tabla = tee_window_waits_table
        result = await self._session.execute(
            select(tabla)
            .where(tabla.c.competition_id == competition_id)
            .order_by(tabla.c.created_at, tabla.c.id)
        )
        return [
            EsperaEnFranja(
                id=uuid.UUID(fila.id),
                competition_id=fila.competition_id,
                round_id=fila.round_id,
                user_id=fila.user_id,
                creada=fila.created_at,
            )
            for fila in result
        ]

    async def vaciar(self, competition_id: CompetitionId) -> None:
        tabla = tee_window_waits_table
        await self._session.execute(delete(tabla).where(tabla.c.competition_id == competition_id))
