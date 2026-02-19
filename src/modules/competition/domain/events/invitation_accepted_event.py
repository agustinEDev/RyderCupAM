"""InvitationAcceptedEvent - Se emite cuando se acepta una invitacion."""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class InvitationAcceptedEvent(DomainEvent):
    """
    Evento emitido cuando un invitado acepta una invitacion.

    Atributos:
        invitation_id: ID de la invitacion (str UUID)
        competition_id: ID de la competicion (str UUID)
        invitee_user_id: ID del usuario que acepto (str UUID)
    """

    invitation_id: str
    competition_id: str
    invitee_user_id: str | None
