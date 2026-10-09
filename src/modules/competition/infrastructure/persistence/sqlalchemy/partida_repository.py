"""Las partidas de stroke play, en Postgres (#251, PR 4)."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.repositories.partida_repository_interface import (
    PartidaRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.competition.domain.value_objects.jugador_de_partida import (
    JugadorDePartida,
)
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.infrastructure.persistence.sqlalchemy.mappers import (
    tee_group_players_table,
    tee_groups_table,
)
from src.modules.user.domain.value_objects.user_id import UserId


class SQLAlchemyPartidaRepository(PartidaRepositoryInterface):
    """Una fila por partida y una por jugador; la hora sale de la hoja, no de aquí."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def reemplazar_franja(self, round_id: RoundId, partidas: Sequence[Partida]) -> None:
        # Los jugadores se van con su partida (ON DELETE CASCADE)
        await self._session.execute(
            delete(tee_groups_table).where(tee_groups_table.c.round_id == round_id)
        )
        ahora = datetime.now(UTC)
        for partida in partidas:
            await self._session.execute(
                tee_groups_table.insert().values(
                    id=str(partida.id),
                    competition_id=partida.competition_id,
                    round_id=partida.round_id,
                    number=partida.numero,
                    status=partida.estado.value,
                    created_at=ahora,
                    updated_at=ahora,
                )
            )
            await self._meter_jugadores(partida)

    async def guardar(self, partidas: Sequence[Partida]) -> None:
        ahora = datetime.now(UTC)
        for partida in partidas:
            await self._session.execute(
                update(tee_groups_table)
                .where(tee_groups_table.c.id == str(partida.id))
                .values(number=partida.numero, status=partida.estado.value, updated_at=ahora)
            )
            await self._session.execute(
                delete(tee_group_players_table).where(
                    tee_group_players_table.c.group_id == str(partida.id)
                )
            )
            await self._meter_jugadores(partida)

    async def borrar(self, partidas: Sequence[Partida]) -> None:
        if not partidas:
            return
        await self._session.execute(
            delete(tee_groups_table).where(tee_groups_table.c.id.in_([str(p.id) for p in partidas]))
        )

    async def find_by_id(self, partida_id: PartidaId) -> Partida | None:
        encontradas = await self._donde(tee_groups_table.c.id == str(partida_id))
        return encontradas[0] if encontradas else None

    async def de_la_franja(self, round_id: RoundId) -> list[Partida]:
        return await self._donde(tee_groups_table.c.round_id == round_id)

    async def de_la_competicion(self, competition_id: CompetitionId) -> list[Partida]:
        return await self._donde(tee_groups_table.c.competition_id == competition_id)

    async def del_jugador(self, competition_id: CompetitionId, user_id: UserId) -> list[Partida]:
        jugadores = tee_group_players_table
        return await self._donde(
            (tee_groups_table.c.competition_id == competition_id)
            & tee_groups_table.c.id.in_(
                select(jugadores.c.group_id).where(jugadores.c.user_id == user_id)
            )
        )

    async def existe_con_jugador(self, user_id: UserId) -> bool:
        jugadores = tee_group_players_table
        return bool(
            await self._session.scalar(select(exists().where(jugadores.c.user_id == user_id)))
        )

    async def _meter_jugadores(self, partida: Partida) -> None:
        if not partida.jugadores:
            return
        await self._session.execute(
            tee_group_players_table.insert(),
            [
                {
                    "group_id": str(partida.id),
                    "round_id": partida.round_id,
                    "user_id": jugador.user_id,
                    "position": posicion,
                    "handicap_index": jugador.handicap,
                    "playing_handicap": jugador.playing_handicap,
                    "tee_color": jugador.tee_color,
                    "tee_gender": jugador.tee_gender,
                    "strokes_by_hole": list(jugador.golpes_por_hoyo),
                    "marks_user_id": partida.marcadores.get(jugador.user_id),
                }
                for posicion, jugador in enumerate(partida.jugadores, start=1)
            ],
        )

    async def _donde(self, condicion) -> list[Partida]:
        """Las partidas que cumplen la condición, por franja y número, con sus jugadores."""
        grupos = (
            await self._session.execute(
                select(tee_groups_table)
                .where(condicion)
                .order_by(tee_groups_table.c.round_id, tee_groups_table.c.number)
            )
        ).all()
        if not grupos:
            return []
        jugadores = tee_group_players_table
        filas = (
            await self._session.execute(
                select(jugadores)
                .where(jugadores.c.group_id.in_([g.id for g in grupos]))
                .order_by(jugadores.c.group_id, jugadores.c.position)
            )
        ).all()
        por_grupo: dict[str, list] = {}
        for fila in filas:
            por_grupo.setdefault(fila.group_id, []).append(fila)
        return [self._partida(grupo, por_grupo.get(grupo.id, [])) for grupo in grupos]

    @staticmethod
    def _partida(grupo, filas) -> Partida:
        return Partida(
            id=PartidaId(uuid.UUID(grupo.id)),
            competition_id=grupo.competition_id,
            round_id=grupo.round_id,
            numero=grupo.number,
            jugadores=[
                JugadorDePartida(
                    user_id=fila.user_id,
                    handicap=fila.handicap_index,
                    playing_handicap=fila.playing_handicap,
                    tee_color=fila.tee_color,
                    tee_gender=fila.tee_gender,
                    golpes_por_hoyo=tuple(fila.strokes_by_hole),
                )
                for fila in filas
            ],
            marcadores={
                fila.user_id: fila.marks_user_id for fila in filas if fila.marks_user_id is not None
            },
            estado=EstadoPartida(grupo.status),
        )
