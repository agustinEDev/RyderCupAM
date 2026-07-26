"""QuickMatchCreatedEvent - Se emite cuando se crea una partida rapida."""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class QuickMatchCreatedEvent(DomainEvent):
    """Evento emitido cuando se crea una partida rapida."""

    quick_match_id: str
    creator_id: str
    golf_course_id: str
    match_format: str
