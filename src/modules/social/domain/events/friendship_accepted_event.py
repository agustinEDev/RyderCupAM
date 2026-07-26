"""FriendshipAcceptedEvent - Se emite cuando se acepta una solicitud de amistad."""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class FriendshipAcceptedEvent(DomainEvent):
    """
    Evento emitido cuando el destinatario acepta una solicitud de amistad.

    Atributos:
        friendship_id: ID de la relacion de amistad (str UUID)
        requester_id: ID del usuario que envio la solicitud (str UUID)
        addressee_id: ID del usuario que acepta (str UUID)
    """

    friendship_id: str
    requester_id: str
    addressee_id: str
