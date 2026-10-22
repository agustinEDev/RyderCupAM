"""Activity Event Repository - SQLAlchemy Implementation."""

from collections.abc import Collection, Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    ColumnElement,
    String,
    and_,
    case,
    cast,
    delete,
    func,
    or_,
    select,
    text,
    tuple_,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivityEventRepositoryInterface,
    ActivitySlice,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.infrastructure.persistence.mappers.activity_event_mapper import (
    activity_events_table,
)
from src.modules.user.domain.value_objects.user_id import UserId

UQ_ACTIVITY_EVENTS_MATCH_TYPE = "uq_activity_events_match_type"


class SQLAlchemyActivityEventRepository(ActivityEventRepositoryInterface):
    """Implementacion asincrona del repositorio de eventos de actividad."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add_many(self, events: list[ActivityEvent]) -> None:
        """
        Publica los eventos de una vuelta, ignorando los que ya estuvieran.

        Se inserta con ON CONFLICT DO NOTHING en lugar de comprobar antes y
        escribir despues. La comprobacion previa deja una ventana entre el "no
        existe" y el INSERT, y dos peticiones que terminan la misma partida a la
        vez —el movil reintentando sobre una conexion mala es el caso tipico—
        caerian dentro de ella. Dejar que decida la clave unica cierra esa
        ventana sin bloquear nada.

        No pasa por la sesion de la ORM a proposito: `session.add_all()` no
        admite ON CONFLICT, y aqui el evento ya nace completo y no se vuelve a
        tocar, asi que no se pierde nada por no tenerlo en el identity map.
        """
        if not events:
            return

        filas = [
            {
                "id": event.id,
                "user_id": event.user_id,
                "type": event.type,
                "occurred_at": event.occurred_at,
                "published_at": event.published_at,
                "visible_to_friends": event.visible_to_friends,
                "payload": event.payload,
                "source_match_id": event.source_match_id,
            }
            for event in events
        ]

        stmt = pg_insert(activity_events_table).values(filas)
        await self._session.execute(
            stmt.on_conflict_do_nothing(constraint=UQ_ACTIVITY_EVENTS_MATCH_TYPE)
        )

    async def find_in(
        self,
        slices: Sequence[ActivitySlice],
        limit: int,
        before: datetime | None = None,
        before_id: UUID | None = None,
    ) -> list[ActivityEvent]:
        condicion = self._condicion(slices)
        if condicion is None:
            return []
        return await self._pagina(condicion, limit, before=before, before_id=before_id)

    async def count_in(
        self, slices: Sequence[ActivitySlice], since: datetime | None, cap: int | None = None
    ) -> int:
        condicion = self._condicion(slices)
        if condicion is None:
            return 0

        # Una fila por tarjeta: los logros de una vuelta de un jugador comparten
        # tarjeta (`ActivityEvent.card_key`); cada aviso va en la suya
        tabla = activity_events_table.c
        logros = sorted(t for t in ActivityEventType if t.is_achievement)
        tarjeta = case(
            (
                tabla.type.in_(logros),
                func.concat(cast(tabla.user_id, String), ":", tabla.source_match_id),
            ),
            else_=cast(tabla.id, String),
        )
        filas = select(tarjeta).where(condicion).distinct()
        if since is not None:
            filas = filas.where(activity_events_table.c.published_at > since)
        if cap is not None:
            # Se cuenta sobre un LIMIT: pasado el tope el numero ya no cambia
            # nada en la pantalla, y asi no se recorre el historial entero
            filas = filas.limit(cap)

        stmt = select(func.count()).select_from(filas.subquery())
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    @staticmethod
    def _condicion(slices: Sequence[ActivitySlice]) -> ColumnElement[bool] | None:
        """
        El WHERE de varios trozos: un OR de (jugadores y tipos), con la
        visibilidad cuando el trozo es de amigos. None si no queda ninguno.
        """
        partes = []
        for trozo in slices:
            if trozo.is_empty:
                continue
            parte = and_(
                activity_events_table.c.user_id.in_(trozo.user_ids),
                activity_events_table.c.type.in_(sorted(trozo.types)),
            )
            if trozo.only_visible_to_friends:
                parte = and_(parte, activity_events_table.c.visible_to_friends.is_(True))
            partes.append(parte)
        return or_(*partes) if partes else None

    async def _pagina(
        self,
        condicion: ColumnElement[bool],
        limit: int,
        before: datetime | None,
        before_id: UUID | None,
    ) -> list[ActivityEvent]:
        stmt = select(ActivityEvent).where(condicion)
        if before is not None:
            # El cursor compara el par entero, no solo la fecha. Todos los
            # eventos de una misma vuelta comparten `published_at` al
            # microsegundo —se publican juntos— asi que filtrar por fecha
            # estricta tiraria tambien los que aun no se han enseñado, y
            # filtrar por `<=` repetiria los ya vistos. El par (fecha, id) si es
            # unico, y `id` desempata de forma estable entre paginas.
            #
            # Un cursor de antes de `published_at` llevaba `occurred_at`: las
            # filas de entonces se rellenaron con esa misma fecha, asi que sigue
            # cayendo en su sitio
            if before_id is not None:
                stmt = stmt.where(
                    tuple_(ActivityEvent._published_at, ActivityEvent._id)
                    < tuple_(before, before_id)
                )
            else:
                stmt = stmt.where(ActivityEvent._published_at < before)

        stmt = stmt.order_by(ActivityEvent._published_at.desc(), ActivityEvent._id.desc()).limit(
            limit
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def exists_for_match(self, match_id: str) -> bool:
        stmt = (
            select(activity_events_table.c.id)
            .where(activity_events_table.c.source_match_id == match_id)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.first() is not None

    async def delete_for_user(
        self, user_id: UserId, types: Collection[ActivityEventType] | None = None
    ) -> int:
        stmt = delete(activity_events_table).where(activity_events_table.c.user_id == user_id)
        if types is not None:
            if not types:
                return 0
            stmt = stmt.where(activity_events_table.c.type.in_(sorted(types)))
        result = await self._session.execute(stmt)
        return result.rowcount or 0

    async def delete_from_source(
        self,
        source_id: str,
        types: Collection[ActivityEventType],
        user_id: UserId | None = None,
    ) -> int:
        if not types:
            return 0
        stmt = delete(activity_events_table).where(
            activity_events_table.c.source_match_id == source_id,
            activity_events_table.c.type.in_(sorted(types)),
        )
        if user_id is not None:
            stmt = stmt.where(activity_events_table.c.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.rowcount or 0

    async def lock_source(self, source_id: str) -> None:
        """
        `pg_advisory_xact_lock`: lo suelta el propio Postgres al acabar la
        transaccion, pase lo que pase. La clave lleva un prefijo para no
        chocar con otros candados por id.
        """
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:clave, 0))"),
            {"clave": f"activity-source:{source_id}"},
        )

    async def find_from_source(
        self, source_id: str, types: Collection[ActivityEventType]
    ) -> list[ActivityEvent]:
        if not types:
            return []
        stmt = select(ActivityEvent).where(
            activity_events_table.c.source_match_id == source_id,
            activity_events_table.c.type.in_(sorted(types)),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete_from_source_for_users(
        self,
        source_id: str,
        types: Collection[ActivityEventType],
        user_ids: Collection[UserId],
    ) -> int:
        if not types or not user_ids:
            return 0
        stmt = delete(activity_events_table).where(
            activity_events_table.c.source_match_id == source_id,
            activity_events_table.c.type.in_(sorted(types)),
            activity_events_table.c.user_id.in_(list(user_ids)),
        )
        result = await self._session.execute(stmt)
        return result.rowcount or 0

    async def delete_for_competition(
        self,
        competition_id: str,
        types: Collection[ActivityEventType],
        user_id: UserId | None = None,
    ) -> int:
        if not types:
            return 0
        stmt = delete(activity_events_table).where(
            activity_events_table.c.payload["competition_id"].astext == competition_id,
            activity_events_table.c.type.in_(sorted(types)),
        )
        if user_id is not None:
            stmt = stmt.where(activity_events_table.c.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.rowcount or 0

    async def hide_from_friends(self, user_id: UserId, types: Collection[ActivityEventType]) -> int:
        if not types:
            return 0
        stmt = (
            update(activity_events_table)
            .where(
                activity_events_table.c.user_id == user_id,
                activity_events_table.c.type.in_(sorted(types)),
                activity_events_table.c.visible_to_friends.is_(True),
            )
            .values(visible_to_friends=False)
        )
        result = await self._session.execute(stmt)
        return result.rowcount or 0
