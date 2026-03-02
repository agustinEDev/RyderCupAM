"""
CompetitionRevertedToClosedEvent - Se emite cuando el torneo revierte a CLOSED.
"""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class CompetitionRevertedToClosedEvent(DomainEvent):
    """
    Evento emitido cuando el torneo revierte de IN_PROGRESS a CLOSED.

    Indica que el creador necesita corregir el schedule (equipos, rondas, matches)
    antes de reiniciar la competición.

    Atributos:
        competition_id: ID de la competición (str UUID)
        name: Nombre del torneo
    """

    competition_id: str
    name: str
