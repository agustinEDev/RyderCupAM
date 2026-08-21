"""QuickMatchStatsIncludedEvent - Un participante vuelve a contar esta partida en sus estadisticas."""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class QuickMatchStatsIncludedEvent(DomainEvent):
    """Contrario de QuickMatchStatsExcludedEvent."""

    quick_match_id: str
    participant_id: str
