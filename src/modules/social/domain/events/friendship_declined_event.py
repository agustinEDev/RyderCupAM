"""FriendshipDeclinedEvent - Se emite cuando se rechaza una solicitud de amistad."""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class FriendshipDeclinedEvent(DomainEvent):
    """
    Evento emitido cuando el destinatario rechaza una solicitud de amistad.

    Atributos:
        friendship_id: ID de la relacion de amistad (str UUID)
        requester_id: ID del usuario que envio la solicitud (str UUID)
        addressee_id: ID del usuario que rechaza (str UUID)
    """

    friendship_id: str
    requester_id: str
    addressee_id: str
