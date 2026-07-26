"""QuickMatchParticipantAddedEvent - Se emite cuando se añade un participante."""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class QuickMatchParticipantAddedEvent(DomainEvent):
    """Evento emitido cuando se añade un participante a una partida rapida."""

    quick_match_id: str
    participant_id: str
    team: str | None
