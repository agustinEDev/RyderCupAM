"""QuickMatchUnhiddenEvent - Se emite cuando un participante vuelve a mostrar la partida."""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class QuickMatchUnhiddenEvent(DomainEvent):
    """Evento emitido cuando un participante deja de ocultar una partida rapida de su historial."""

    quick_match_id: str
    participant_id: str
