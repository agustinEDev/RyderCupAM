"""InvitationCreatedEvent - Se emite cuando se crea una invitacion."""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class InvitationCreatedEvent(DomainEvent):
    """
    Evento emitido cuando se crea una invitacion a una competicion.

    Atributos:
        invitation_id: ID de la invitacion (str UUID)
        competition_id: ID de la competicion (str UUID)
        inviter_id: ID del usuario que invita (str UUID)
        invitee_email: Email del invitado
    """

    invitation_id: str
    competition_id: str
    inviter_id: str
    invitee_email: str
