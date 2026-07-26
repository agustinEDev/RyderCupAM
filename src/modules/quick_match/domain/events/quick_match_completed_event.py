"""QuickMatchCompletedEvent - Se emite cuando finaliza una partida rapida."""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class QuickMatchCompletedEvent(DomainEvent):
    """Evento emitido cuando una partida rapida pasa a COMPLETED."""

    quick_match_id: str
