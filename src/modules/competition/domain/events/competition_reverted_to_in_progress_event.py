"""
CompetitionRevertedToInProgressEvent - Se emite cuando el torneo revierte a IN_PROGRESS.
"""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class CompetitionRevertedToInProgressEvent(DomainEvent):
    """
    Evento emitido cuando el torneo revierte de COMPLETED a IN_PROGRESS.

    Indica que el creador ha reabierto un torneo ya finalizado, por ejemplo
    para añadir una ronda adicional. No afecta a los partidos ya completados.

    Atributos:
        competition_id: ID de la competición (str UUID)
        name: Nombre del torneo
    """

    competition_id: str
    name: str
