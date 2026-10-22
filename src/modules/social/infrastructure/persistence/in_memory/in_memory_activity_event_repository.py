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
        # En memoria no hay tabla de competiciones: los tests dicen aqui que
        # torneos son privados para `skip_private_enrollments`
        self.private_competition_ids: set[str] = set()
        # Ni las invitaciones: las que siguen abiertas, para `open_invitations_at`
        # (None = no se filtra)
        self.open_invitation_ids: set[str] | None = None
        # Ni las partidas rapidas: las (partida, autor) que el autor tiene en su
        # papelera, para `hide_trashed_quick_matches_from`
        self.trashed_quick_matches: set[tuple[str, UserId]] = set()
        # Avisos de salida retirados por un cambio: (ronda, jugador) -> torneo
        self._salidas_retiradas: dict[tuple[str, UserId], str] = {}

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
        self,
        slices: Sequence[ActivitySlice],
        since: datetime | None,
        cap: int | None = None,
        skip_private_enrollments: bool = False,
        open_invitations_at: datetime | None = None,
        hide_trashed_quick_matches_from: UserId | None = None,
    ) -> int:
        # Por tarjetas, como el SQL: los logros de una vuelta son una
        cuenta = len(
            {
                e.card_key
                for e in self._events
                if self._entra(e, slices)
                and (since is None or e.published_at > since)
                and not (skip_private_enrollments and self._apuntado_a_privado(e))
                and not (open_invitations_at is not None and self._invitacion_cerrada(e))
                and not (
                    hide_trashed_quick_matches_from is not None
                    and self._en_la_papelera_de_otro(e, hide_trashed_quick_matches_from)
                )
            }
        )
        return cuenta if cap is None else min(cuenta, cap)

    def _en_la_papelera_de_otro(self, event: ActivityEvent, viewer_id: UserId) -> bool:
        return (
            event.user_id != viewer_id
            and event.comes_from_a_quick_match
            and (event.source_match_id, event.user_id) in self.trashed_quick_matches
        )

    def _invitacion_cerrada(self, event: ActivityEvent) -> bool:
        return (
            event.type == ActivityEventType.INVITED_TO_TOURNAMENT
            and self.open_invitation_ids is not None
            and event.source_match_id not in self.open_invitation_ids
        )

    def _apuntado_a_privado(self, event: ActivityEvent) -> bool:
        return (
            event.type == ActivityEventType.ENROLLED_IN_TOURNAMENT
            and event.payload.get("competition_id") in self.private_competition_ids
        )

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
        # Como en SQL: una lista de tipos vacia es "ninguno", no "todos"
        if types is not None and not types:
            return 0
        antes = len(self._events)
        self._events = [
            e
            for e in self._events
            if not (e.user_id == user_id and (types is None or e.type in types))
        ]
        return antes - len(self._events)

    async def delete_pairs(
        self, type: ActivityEventType, pairs: Sequence[tuple[UserId, str]]
    ) -> int:
        parejas = set(pairs)
        antes = len(self._events)
        self._events = [
            e
            for e in self._events
            if not (e.type == type and (e.user_id, e.source_match_id) in parejas)
        ]
        return antes - len(self._events)

    async def delete_from_source(
        self,
        source_id: str,
        types: Collection[ActivityEventType],
        user_id: UserId | None = None,
    ) -> int:
        antes = len(self._events)
        self._events = [
            e
            for e in self._events
            if not (
                e.source_match_id == source_id
                and e.type in types
                and (user_id is None or e.user_id == user_id)
            )
        ]
        return antes - len(self._events)

    async def lock_scope(self, scope_id: str) -> None:
        """En memoria no hay nada a la vez: no hay nada que bloquear."""
        return

    async def find_from_source(
        self, source_id: str, types: Collection[ActivityEventType]
    ) -> list[ActivityEvent]:
        return [e for e in self._events if e.source_match_id == source_id and e.type in types]

    async def last_published_at(
        self, competition_id: str, types: Collection[ActivityEventType]
    ) -> datetime | None:
        fechas = [
            e.published_at
            for e in self._events
            if e.type in types and e.payload.get("competition_id") == competition_id
        ]
        return max(fechas, default=None)

    async def find_for_users(
        self, user_ids: Collection[UserId], types: Collection[ActivityEventType]
    ) -> list[ActivityEvent]:
        quienes = set(user_ids)
        return [e for e in self._events if e.user_id in quienes and e.type in types]

    async def delete_from_source_for_users(
        self,
        source_id: str,
        types: Collection[ActivityEventType],
        user_ids: Collection[UserId],
    ) -> int:
        quienes = set(user_ids)
        antes = len(self._events)
        self._events = [
            e
            for e in self._events
            if not (e.source_match_id == source_id and e.type in types and e.user_id in quienes)
        ]
        return antes - len(self._events)

    async def delete_for_competition(
        self,
        competition_id: str,
        types: Collection[ActivityEventType],
        user_id: UserId | None = None,
    ) -> int:
        antes = len(self._events)
        self._events = [
            e
            for e in self._events
            if not (
                e.type in types
                and e.payload.get("competition_id") == competition_id
                and (user_id is None or e.user_id == user_id)
            )
        ]
        return antes - len(self._events)

    async def replace_for_competition(
        self,
        competition_id: str,
        types: Collection[ActivityEventType],
        events: list[ActivityEvent],
    ) -> None:
        nuevos = {(e.user_id, e.source_match_id, e.type): e for e in events}

        def _sobra(e: ActivityEvent) -> bool:
            if e.type not in types or e.payload.get("competition_id") != competition_id:
                return False
            nuevo = nuevos.get((e.user_id, e.source_match_id, e.type))
            return (
                nuevo is None
                or nuevo.payload != e.payload
                or nuevo.visible_to_friends != e.visible_to_friends
            )

        self._events = [e for e in self._events if not _sobra(e)]
        await self.add_many(events)

    async def hide_from_friends(self, user_id: UserId, types: Collection[ActivityEventType]) -> int:
        ocultos = 0
        for e in self._events:
            if e.user_id == user_id and e.type in types and e.visible_to_friends:
                e.hide_from_friends()
                ocultos += 1
        return ocultos

    async def remember_withdrawn_tee_times(
        self, round_id: str, competition_id: str, user_ids: Collection[UserId]
    ) -> None:
        for user_id in user_ids:
            self._salidas_retiradas[(round_id, user_id)] = competition_id

    async def withdrawn_tee_times(self, round_id: str) -> set[UserId]:
        return {user_id for ronda, user_id in self._salidas_retiradas if ronda == round_id}

    async def forget_withdrawn_tee_times(self, round_id: str, user_ids: Collection[UserId]) -> None:
        for user_id in user_ids:
            self._salidas_retiradas.pop((round_id, user_id), None)

    async def forget_withdrawn_tee_times_of_competition(
        self, competition_id: str, user_id: UserId | None = None
    ) -> None:
        self._salidas_retiradas = {
            clave: torneo
            for clave, torneo in self._salidas_retiradas.items()
            if torneo != competition_id or (user_id is not None and clave[1] != user_id)
        }
