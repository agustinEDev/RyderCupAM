"""
CompetitionCompletedEvent - Se emite cuando el torneo finaliza.
"""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class CompetitionCompletedEvent(DomainEvent):
    """
    Evento emitido cuando el torneo finaliza.

    Indica que el torneo ha concluido.
    Otros módulos pueden:
    - Calcular estadísticas finales
    - Generar reportes
    - Enviar certificados/diplomas
    - Archivar datos

    Atributos:
        competition_id: ID de la competición (str UUID)
        name: Nombre del torneo
    """

    competition_id: str
    name: str
