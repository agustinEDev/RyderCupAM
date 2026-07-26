"""
Friendship Entity - Representa una relacion de amistad entre dos usuarios.

Esta entidad gestiona el ciclo de vida de una solicitud/relacion de amistad.
"""

from datetime import datetime

from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.events.domain_event import DomainEvent

from ..events.friendship_accepted_event import FriendshipAcceptedEvent
from ..events.friendship_blocked_event import FriendshipBlockedEvent
from ..events.friendship_declined_event import FriendshipDeclinedEvent
from ..events.friendship_requested_event import FriendshipRequestedEvent
from ..exceptions.social_violations import (
    InvalidFriendshipStatusViolation,
    SelfFriendRequestViolation,
)
from ..value_objects.friendship_id import FriendshipId
from ..value_objects.friendship_status import FriendshipStatus


class Friendship:
    """
    Entidad Friendship - Representa una relacion de amistad entre dos usuarios.

    Gestiona:
    - Envio de solicitudes de amistad
    - Respuesta (aceptar/rechazar)
    - Bloqueo

    Invariantes:
    - requester_id y addressee_id no pueden ser None
    - Solo PENDING permite aceptar/rechazar
    - Solo PENDING o ACCEPTED permiten bloquear
    """

    def __init__(
        self,
        id: FriendshipId,
        requester_id: UserId,
        addressee_id: UserId,
        status: FriendshipStatus,
        blocked_by: UserId | None = None,
        responded_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        domain_events: list[DomainEvent] | None = None,
    ):
        self._id = id
        self._requester_id = requester_id
        self._addressee_id = addressee_id
        self._status = status
        self._blocked_by = blocked_by
        self._responded_at = responded_at
        self._created_at = created_at or datetime.now()
        self._updated_at = updated_at or datetime.now()
        self._domain_events: list[DomainEvent] = domain_events or []

    # ===========================================
    # FACTORY METHODS
    # ===========================================

    @classmethod
    def create(
        cls,
        id: FriendshipId,
        requester_id: UserId,
        addressee_id: UserId,
    ) -> "Friendship":
        """Factory method para crear una nueva solicitud de amistad con status PENDING."""
        if requester_id == addressee_id:
            raise SelfFriendRequestViolation("No puedes enviarte una solicitud a ti mismo.")

        now = datetime.now()
        friendship = cls(
            id=id,
            requester_id=requester_id,
            addressee_id=addressee_id,
            status=FriendshipStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

        event = FriendshipRequestedEvent(
            friendship_id=str(friendship._id),
            requester_id=str(friendship._requester_id),
            addressee_id=str(friendship._addressee_id),
        )
        friendship.add_domain_event(event)

        return friendship

    @classmethod
    def create_blocked(
        cls,
        id: FriendshipId,
        blocker_id: UserId,
        blocked_id: UserId,
    ) -> "Friendship":
        """
        Factory method para bloquear directamente a un usuario sin amistad previa.

        El bloqueador queda registrado como `requester_id` por convencion de
        almacenamiento, pero la autoridad real sobre quien bloqueo se guarda en
        `blocked_by`.
        """
        if blocker_id == blocked_id:
            raise SelfFriendRequestViolation("No puedes bloquearte a ti mismo.")

        now = datetime.now()
        friendship = cls(
            id=id,
            requester_id=blocker_id,
            addressee_id=blocked_id,
            status=FriendshipStatus.BLOCKED,
            blocked_by=blocker_id,
            responded_at=now,
            created_at=now,
            updated_at=now,
        )

        event = FriendshipBlockedEvent(
            friendship_id=str(friendship._id),
            blocker_id=str(blocker_id),
            blocked_id=str(blocked_id),
        )
        friendship.add_domain_event(event)

        return friendship

    @classmethod
    def reconstruct(
        cls,
        id: FriendshipId,
        requester_id: UserId,
        addressee_id: UserId,
        status: FriendshipStatus,
        blocked_by: UserId | None = None,
        responded_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> "Friendship":
        """Reconstruye una amistad desde la base de datos (sin domain events)."""
        return cls(
            id=id,
            requester_id=requester_id,
            addressee_id=addressee_id,
            status=status,
            blocked_by=blocked_by,
            responded_at=responded_at,
            created_at=created_at,
            updated_at=updated_at,
        )

    # ===========================================
    # PROPERTIES (Encapsulacion — solo lectura)
    # ===========================================

    @property
    def id(self) -> FriendshipId:
        return self._id

    @property
    def requester_id(self) -> UserId:
        return self._requester_id

    @property
    def addressee_id(self) -> UserId:
        return self._addressee_id

    @property
    def status(self) -> FriendshipStatus:
        return self._status

    @property
    def blocked_by(self) -> UserId | None:
        return self._blocked_by

    @property
    def responded_at(self) -> datetime | None:
        return self._responded_at

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    # ===========================================
    # METODOS DE CONSULTA (QUERIES)
    # ===========================================

    def is_pending(self) -> bool:
        return self._status.is_pending()

    def is_accepted(self) -> bool:
        return self._status.is_accepted()

    def is_blocked(self) -> bool:
        return self._status.is_blocked()

    def involves_user(self, user_id: UserId) -> bool:
        """Verifica si el usuario dado participa en esta relacion (requester o addressee)."""
        return user_id in (self._requester_id, self._addressee_id)

    def other_user_id(self, user_id: UserId) -> UserId:
        """Devuelve el ID del otro usuario de la relacion, dado uno de los dos participantes."""
        if self._requester_id == user_id:
            return self._addressee_id
        if self._addressee_id == user_id:
            return self._requester_id
        raise ValueError("El usuario indicado no participa en esta relacion de amistad.")

    # ===========================================
    # METODOS DE COMANDO (CAMBIOS DE ESTADO)
    # ===========================================

    def accept(self) -> None:
        """Acepta la solicitud de amistad (PENDING -> ACCEPTED)."""
        if not self._status.can_transition_to(FriendshipStatus.ACCEPTED):
            raise InvalidFriendshipStatusViolation(
                f"Cannot accept friendship request in status {self._status.value}."
            )

        now = datetime.now()
        self._status = FriendshipStatus.ACCEPTED
        self._responded_at = now
        self._updated_at = now

        event = FriendshipAcceptedEvent(
            friendship_id=str(self._id),
            requester_id=str(self._requester_id),
            addressee_id=str(self._addressee_id),
        )
        self.add_domain_event(event)

    def decline(self) -> None:
        """Rechaza la solicitud de amistad (PENDING -> DECLINED)."""
        if not self._status.can_transition_to(FriendshipStatus.DECLINED):
            raise InvalidFriendshipStatusViolation(
                f"Cannot decline friendship request in status {self._status.value}."
            )

        now = datetime.now()
        self._status = FriendshipStatus.DECLINED
        self._responded_at = now
        self._updated_at = now

        event = FriendshipDeclinedEvent(
            friendship_id=str(self._id),
            requester_id=str(self._requester_id),
            addressee_id=str(self._addressee_id),
        )
        self.add_domain_event(event)

    def block(self, blocker_id: UserId) -> None:
        """Bloquea la relacion (PENDING/ACCEPTED -> BLOCKED)."""
        if not self._status.can_transition_to(FriendshipStatus.BLOCKED):
            raise InvalidFriendshipStatusViolation(
                f"Cannot block friendship in status {self._status.value}."
            )

        now = datetime.now()
        self._status = FriendshipStatus.BLOCKED
        self._blocked_by = blocker_id
        self._responded_at = now
        self._updated_at = now

        event = FriendshipBlockedEvent(
            friendship_id=str(self._id),
            blocker_id=str(blocker_id),
            blocked_id=str(self.other_user_id(blocker_id)),
        )
        self.add_domain_event(event)

    # ===========================================
    # DOMAIN EVENTS
    # ===========================================

    def add_domain_event(self, event: DomainEvent) -> None:
        """Registra un evento de dominio en la entidad."""
        if not hasattr(self, "_domain_events") or self._domain_events is None:
            self._domain_events = []
        self._domain_events.append(event)

    def get_domain_events(self) -> list[DomainEvent]:
        if not hasattr(self, "_domain_events") or self._domain_events is None:
            self._domain_events = []
        return self._domain_events.copy()

    def clear_domain_events(self) -> None:
        self._domain_events = []

    # ===========================================
    # METODOS ESPECIALES
    # ===========================================

    def __str__(self) -> str:
        return f"Friendship({self._requester_id} -> {self._addressee_id}, {self._status.value})"

    def __eq__(self, other) -> bool:
        return isinstance(other, Friendship) and self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)
