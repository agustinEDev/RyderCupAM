"""QuickMatchParticipantRemovedEvent - Se emite cuando se elimina un participante."""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class QuickMatchParticipantRemovedEvent(DomainEvent):
    """Evento emitido cuando se elimina un participante de una partida rapida."""

    quick_match_id: str
    user_id: str
