"""In-Memory Activity Event Repository para testing."""

from datetime import datetime

from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivityEventRepositoryInterface,
)
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
        self, user_ids: list[UserId], limit: int, before: datetime | None = None
    ) -> list[ActivityEvent]:
        encontrados = [e for e in self._events if e.user_id in user_ids]
        if before is not None:
            encontrados = [e for e in encontrados if e.occurred_at < before]

        encontrados.sort(key=lambda e: (e.occurred_at, str(e.id)), reverse=True)
        return encontrados[:limit]

    async def count_for_users_since(self, user_ids: list[UserId], since: datetime) -> int:
        return len(
            [e for e in self._events if e.user_id in user_ids and e.occurred_at > since]
        )

    async def exists_for_match(self, match_id: str) -> bool:
        return any(e.source_match_id == match_id for e in self._events)

    async def delete_for_user(self, user_id: UserId) -> int:
        antes = len(self._events)
        self._events = [e for e in self._events if e.user_id != user_id]
        return antes - len(self._events)
