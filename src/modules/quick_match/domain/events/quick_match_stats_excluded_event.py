"""QuickMatchStatsExcludedEvent - Un participante deja esta partida fuera de sus estadisticas."""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class QuickMatchStatsExcludedEvent(DomainEvent):
    """
    Emitido cuando un participante marca la partida para que no cuente en sus
    estadisticas. No la saca de su historial: eso es QuickMatchHiddenEvent.
    """

    quick_match_id: str
    participant_id: str
