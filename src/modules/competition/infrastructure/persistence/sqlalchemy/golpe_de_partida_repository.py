"""Los golpes de las partidas de stroke play, en Postgres (#251, PR 5)."""

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.competition.domain.entities.golpe_de_partida import GolpeDePartida
from src.modules.competition.domain.repositories.golpe_de_partida_repository_interface import (
    GolpeDePartidaRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.infrastructure.persistence.sqlalchemy.mappers import (
    tee_group_hole_scores_table,
)

tabla = tee_group_hole_scores_table


class SQLAlchemyGolpeDePartidaRepository(GolpeDePartidaRepositoryInterface):
    """Una fila por partida, jugador y hoyo."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def guardar(self, golpe: GolpeDePartida) -> None:
        valores = {
            "group_id": str(golpe.partida_id),
            "user_id": golpe.user_id,
            "hole_number": golpe.hoyo,
            "round_id": golpe.round_id,
            "competition_id": golpe.competition_id,
            "own_score": golpe.propio,
            "own_submitted": golpe.propio_enviado,
            "own_by": golpe.propio_por,
            "marker_score": golpe.del_marcador,
            "marker_submitted": golpe.marcador_enviado,
            "marker_by": golpe.marcador_por,
            "created_at": golpe.creado,
            "updated_at": golpe.actualizado,
        }
        cambios = {k: v for k, v in valores.items() if k not in ("created_at",)}
        await self._session.execute(
            insert(tabla)
            .values(**valores)
            .on_conflict_do_update(
                index_elements=["group_id", "user_id", "hole_number"], set_=cambios
            )
        )

    async def de_la_partida(self, partida_id: PartidaId) -> list[GolpeDePartida]:
        return await self._donde(tabla.c.group_id == str(partida_id))

    async def de_la_franja(self, round_id: RoundId) -> list[GolpeDePartida]:
        return await self._donde(tabla.c.round_id == round_id)

    async def de_la_competicion(self, competition_id: CompetitionId) -> list[GolpeDePartida]:
        return await self._donde(tabla.c.competition_id == competition_id)

    async def _donde(self, condicion) -> list[GolpeDePartida]:
        filas = await self._session.execute(
            select(tabla)
            .where(condicion)
            .order_by(tabla.c.group_id, tabla.c.user_id, tabla.c.hole_number)
        )
        return [
            GolpeDePartida(
                partida_id=PartidaId(uuid.UUID(f.group_id)),
                round_id=f.round_id,
                competition_id=f.competition_id,
                user_id=f.user_id,
                hoyo=f.hole_number,
                propio=f.own_score,
                propio_enviado=f.own_submitted,
                propio_por=f.own_by,
                del_marcador=f.marker_score,
                marcador_enviado=f.marker_submitted,
                marcador_por=f.marker_by,
                creado=f.created_at,
                actualizado=f.updated_at,
            )
            for f in filas
        ]
