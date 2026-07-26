"""FriendshipRequestedEvent - Se emite cuando se envia una solicitud de amistad."""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class FriendshipRequestedEvent(DomainEvent):
    """
    Evento emitido cuando un usuario envia una solicitud de amistad a otro.

    Atributos:
        friendship_id: ID de la relacion de amistad (str UUID)
        requester_id: ID del usuario que envia la solicitud (str UUID)
        addressee_id: ID del usuario destinatario (str UUID)
    """

    friendship_id: str
    requester_id: str
    addressee_id: str
