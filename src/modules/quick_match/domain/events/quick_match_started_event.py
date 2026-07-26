"""QuickMatchStartedEvent - Se emite cuando se inicia una partida rapida."""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class QuickMatchStartedEvent(DomainEvent):
    """Evento emitido cuando una partida rapida pasa a IN_PROGRESS."""

    quick_match_id: str
