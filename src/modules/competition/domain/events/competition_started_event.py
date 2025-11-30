"""
CompetitionStartedEvent - Se emite cuando el torneo comienza (IN_PROGRESS).
"""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class CompetitionStartedEvent(DomainEvent):
    """
    Evento emitido cuando el torneo comienza.

    Indica que el torneo está oficialmente en curso.
    Otros módulos pueden:
    - Inicializar sistema de scoring en vivo
    - Enviar recordatorios a jugadores
    - Activar funciones de seguimiento en tiempo real

    Atributos:
        competition_id: ID de la competición (str UUID)
        name: Nombre del torneo
    """

    competition_id: str
    name: str
