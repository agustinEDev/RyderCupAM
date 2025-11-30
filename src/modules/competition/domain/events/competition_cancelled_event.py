"""
CompetitionCancelledEvent - Se emite cuando se cancela el torneo.
"""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class CompetitionCancelledEvent(DomainEvent):
    """
    Evento emitido cuando se cancela un torneo.

    Indica que el torneo no se realizará.
    Otros módulos pueden:
    - Notificar a todos los jugadores inscritos
    - Procesar reembolsos (si aplica)
    - Liberar recursos reservados

    Atributos:
        competition_id: ID de la competición (str UUID)
        name: Nombre del torneo
        reason: Razón de la cancelación (opcional)
    """

    competition_id: str
    name: str
    reason: str | None = None
