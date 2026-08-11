"""Activity Event Repository - SQLAlchemy Implementation."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivityEventRepositoryInterface,
)
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
                "payload": event.payload,
                "source_match_id": event.source_match_id,
            }
            for event in events
        ]

        stmt = pg_insert(activity_events_table).values(filas)
        await self._session.execute(
            stmt.on_conflict_do_nothing(constraint=UQ_ACTIVITY_EVENTS_MATCH_TYPE)
        )

    async def find_for_users(
        self,
        user_ids: list[UserId],
        limit: int,
        before: datetime | None = None,
        before_id: UUID | None = None,
    ) -> list[ActivityEvent]:
        if not user_ids:
            return []

        stmt = select(ActivityEvent).where(ActivityEvent._user_id.in_(user_ids))
        if before is not None:
            # El cursor compara el par entero, no solo la fecha. Todos los
            # eventos de una misma vuelta comparten `occurred_at` al
            # microsegundo —salen del mismo `created_at`— asi que filtrar por
            # fecha estricta tiraria tambien los que aun no se han enseñado, y
            # filtrar por `<=` repetiria los ya vistos. El par (fecha, id) si es
            # unico, y `id` desempata de forma estable entre paginas
            if before_id is not None:
                stmt = stmt.where(
                    tuple_(ActivityEvent._occurred_at, ActivityEvent._id)
                    < tuple_(before, before_id)
                )
            else:
                stmt = stmt.where(ActivityEvent._occurred_at < before)

        stmt = stmt.order_by(
            ActivityEvent._occurred_at.desc(), ActivityEvent._id.desc()
        ).limit(limit)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_users_since(self, user_ids: list[UserId], since: datetime) -> int:
        if not user_ids:
            return 0

        stmt = (
            select(func.count())
            .select_from(activity_events_table)
            .where(
                activity_events_table.c.user_id.in_(user_ids),
                activity_events_table.c.occurred_at > since,
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def exists_for_match(self, match_id: str) -> bool:
        stmt = (
            select(activity_events_table.c.id)
            .where(activity_events_table.c.source_match_id == match_id)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.first() is not None

    async def delete_for_user(self, user_id: UserId) -> int:
        stmt = delete(activity_events_table).where(
            activity_events_table.c.user_id == user_id
        )
        result = await self._session.execute(stmt)
        return result.rowcount or 0
