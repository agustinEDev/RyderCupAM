"""In-Memory Activity Event Repository para testing."""

from collections.abc import Collection, Sequence
from datetime import datetime
from uuid import UUID

from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivityEventRepositoryInterface,
    ActivitySlice,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.user.domain.value_objects.user_id import UserId


class InMemoryActivityEventRepository(ActivityEventRepositoryInterface):
    """Implementacion en memoria del repositorio de eventos de actividad."""

    def __init__(self):
        self._events: list[ActivityEvent] = []

    async def add_many(self, events: list[ActivityEvent]) -> None:
        """
        Publica los eventos nuevos y descarta los repetidos.

        Reproduce la clave unica de la tabla —(user_id, source_match_id, type)—
        porque es una regla del modelo, no un detalle de Postgres: si aqui se
        aceptara el duplicado, los tests de los casos de uso pasarian con una
        idempotencia que en produccion depende de la base de datos.
        """
        for event in events:
            if not self._existe(event):
                self._events.append(event)

    def _existe(self, event: ActivityEvent) -> bool:
        return any(
            e.user_id == event.user_id
            and e.source_match_id == event.source_match_id
            and e.type == event.type
            for e in self._events
        )

    async def find_for_users(
        self,
        user_ids: list[UserId],
        limit: int,
        before: datetime | None = None,
        before_id: UUID | None = None,
    ) -> list[ActivityEvent]:
        encontrados = [e for e in self._events if e.user_id in user_ids]
        return self._pagina(encontrados, limit, before, before_id)

    async def find_in(
        self,
        slices: Sequence[ActivitySlice],
        limit: int,
        before: datetime | None = None,
        before_id: UUID | None = None,
    ) -> list[ActivityEvent]:
        encontrados = [e for e in self._events if self._entra(e, slices)]
        return self._pagina(encontrados, limit, before, before_id)

    async def count_in(
        self, slices: Sequence[ActivitySlice], since: datetime | None, cap: int | None = None
    ) -> int:
        cuenta = len(
            [
                e
                for e in self._events
                if self._entra(e, slices) and (since is None or e.published_at > since)
            ]
        )
        return cuenta if cap is None else min(cuenta, cap)

    @staticmethod
    def _entra(event: ActivityEvent, slices: Sequence[ActivitySlice]) -> bool:
        return any(
            event.user_id in trozo.user_ids
            and event.type in trozo.types
            and (event.visible_to_friends or not trozo.only_visible_to_friends)
            for trozo in slices
        )

    @staticmethod
    def _pagina(
        encontrados: list[ActivityEvent],
        limit: int,
        before: datetime | None,
        before_id: UUID | None,
    ) -> list[ActivityEvent]:
        if before is not None:
            # El mismo par (fecha, id) que compara el SQL: sin el id, los eventos
            # de una misma vuelta —que comparten `published_at`— se perderian al
            # pasar de pagina
            if before_id is not None:
                encontrados = [
                    e for e in encontrados if (e.published_at, str(e.id)) < (before, str(before_id))
                ]
            else:
                encontrados = [e for e in encontrados if e.published_at < before]

        encontrados.sort(key=lambda e: (e.published_at, str(e.id)), reverse=True)
        return encontrados[:limit]

    async def exists_for_match(self, match_id: str) -> bool:
        return any(e.source_match_id == match_id for e in self._events)

    async def delete_for_user(
        self, user_id: UserId, types: Collection[ActivityEventType] | None = None
    ) -> int:
        antes = len(self._events)
        self._events = [
            e
            for e in self._events
            if not (e.user_id == user_id and (types is None or e.type in types))
        ]
        return antes - len(self._events)

    async def hide_from_friends(self, user_id: UserId, types: Collection[ActivityEventType]) -> int:
        ocultos = 0
        for e in self._events:
            if e.user_id == user_id and e.type in types and e.visible_to_friends:
                e.hide_from_friends()
                ocultos += 1
        return ocultos
