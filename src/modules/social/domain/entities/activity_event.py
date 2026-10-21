"""Entidad: ActivityEvent — un logro publicado en el feed de los amigos."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.user.domain.value_objects.user_id import UserId


class ActivityEvent:
    """
    Algo que un jugador ha conseguido y que sus amigos verán.

    **La partida de la que sale es obligatoria** (`source_match_id`) por dos
    razones: para poder enlazar al detalle desde el feed, y para no duplicar.
    Completar una partida dos veces —o reprocesarla— no debe llenar el feed de
    entradas repetidas, así que la pareja `(source_match_id, type)` es única por
    jugador.

    Que sea obligatoria no es un detalle: en Postgres un NULL no es igual a otro
    NULL, así que un evento sin partida se escaparía de esa clave única y podría
    publicarse tantas veces como se reprocesara. Todos los logros nacen de una
    vuelta terminada —incluidos `NEW_COURSE`, `FIRST_TOURNAMENT` y
    `PERSONAL_BEST`, que también salen de una partida concreta— así que exigirla
    no deja fuera ningún caso real y sí cierra ese hueco.

    El evento es inmutable: un logro ocurrió o no ocurrió. Si deja de ser
    publicable (se borra la partida) se borra; no se edita. La única excepción
    es `visible_to_friends`, que apagar la publicación pone a False.

    **Dos fechas distintas.** `occurred_at` es cuándo se jugó (el día de la
    ronda, la creación de la partida rápida); `published_at`, cuándo llegó al
    feed. Un torneo publica al cerrarse vueltas de hace días, así que el orden
    del feed y el aviso de novedades van por la segunda.
    """

    def __init__(
        self,
        id: UUID,
        user_id: UserId,
        type: ActivityEventType,
        occurred_at: datetime,
        source_match_id: str,
        payload: dict | None = None,
        published_at: datetime | None = None,
        visible_to_friends: bool = True,
    ):
        if not isinstance(user_id, UserId):
            raise TypeError("user_id must be a UserId")
        if not isinstance(type, ActivityEventType):
            raise TypeError("type must be an ActivityEventType")
        if not source_match_id:
            raise ValueError("source_match_id is required: every event comes from a round")

        self._id = id
        self._user_id = user_id
        self._type = type
        self._occurred_at = occurred_at
        self._payload = dict(payload or {})
        self._source_match_id = source_match_id
        # En UTC y sin zona, como el resto de fechas que se guardan
        self._published_at = published_at or datetime.now(UTC).replace(tzinfo=None)
        # Con la publicación apagada el logro se guarda igual, pero solo para
        # su autor: encenderla después no lo destapa
        self._visible_to_friends = visible_to_friends

    # === Factory Methods ===

    @classmethod
    def create(
        cls,
        user_id: UserId,
        type: ActivityEventType,
        occurred_at: datetime,
        source_match_id: str,
        payload: dict | None = None,
        published_at: datetime | None = None,
        visible_to_friends: bool = True,
    ) -> "ActivityEvent":
        return cls(
            id=uuid4(),
            user_id=user_id,
            type=type,
            occurred_at=occurred_at,
            payload=payload,
            source_match_id=source_match_id,
            published_at=published_at,
            visible_to_friends=visible_to_friends,
        )

    @classmethod
    def reconstruct(cls, **props) -> "ActivityEvent":
        return cls(**props)

    # === Getters ===

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def user_id(self) -> UserId:
        return self._user_id

    @property
    def type(self) -> ActivityEventType:
        return self._type

    @property
    def occurred_at(self) -> datetime:
        return self._occurred_at

    @property
    def published_at(self) -> datetime:
        return self._published_at

    @property
    def visible_to_friends(self) -> bool:
        return self._visible_to_friends

    @property
    def payload(self) -> dict:
        return dict(self._payload)

    @property
    def source_match_id(self) -> str:
        return self._source_match_id

    # === Business Rules ===

    def is_from(self, match_id: str) -> bool:
        return self._source_match_id == match_id

    def hide_from_friends(self) -> None:
        """Deja de verlo nadie mas que su autor (apagar la publicacion)."""
        self._visible_to_friends = False

    def __eq__(self, other) -> bool:
        return isinstance(other, ActivityEvent) and self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f"<ActivityEvent {self._type.value} user={self._user_id.value}>"
