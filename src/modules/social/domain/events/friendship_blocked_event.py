"""FriendshipBlockedEvent - Se emite cuando un usuario bloquea a otro."""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class FriendshipBlockedEvent(DomainEvent):
    """
    Evento emitido cuando un usuario bloquea a otro (con o sin amistad previa).

    Atributos:
        friendship_id: ID de la relacion de amistad (str UUID)
        blocker_id: ID del usuario que bloquea (str UUID)
        blocked_id: ID del usuario bloqueado (str UUID)
    """

    friendship_id: str
    blocker_id: str
    blocked_id: str
