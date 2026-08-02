"""QuickMatchHiddenEvent - Se emite cuando un participante oculta la partida de su historial."""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class QuickMatchHiddenEvent(DomainEvent):
    """Evento emitido cuando un participante oculta una partida rapida de su propio historial."""

    quick_match_id: str
    participant_id: str
