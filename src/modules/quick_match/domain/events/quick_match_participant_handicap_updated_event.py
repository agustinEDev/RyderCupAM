"""QuickMatchParticipantHandicapUpdatedEvent - Se emite al editar el handicap de un participante."""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class QuickMatchParticipantHandicapUpdatedEvent(DomainEvent):
    """Evento emitido cuando el creador edita el handicap (manual u override) de un participante."""

    quick_match_id: str
    participant_id: str
    handicap: float | None
