"""
CompetitionEnrollmentsReopenedEvent - Se emite cuando se reabren las inscripciones.
"""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class CompetitionEnrollmentsReopenedEvent(DomainEvent):
    """
    Evento emitido cuando las inscripciones se reabren (CLOSED -> ACTIVE).

    Indica que el creador necesita añadir o modificar jugadores
    antes de volver a cerrar inscripciones.

    Atributos:
        competition_id: ID de la competición (str UUID)
        name: Nombre del torneo
    """

    competition_id: str
    name: str
