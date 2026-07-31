"""QuickMatchCancelledEvent - Se emite cuando se cancela una partida rapida."""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class QuickMatchCancelledEvent(DomainEvent):
    """Evento emitido cuando una partida rapida pasa a CANCELLED."""

    quick_match_id: str
