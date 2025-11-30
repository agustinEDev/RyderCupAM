"""
CompetitionCreatedEvent - Se emite cuando se crea una nueva competición.
"""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class CompetitionCreatedEvent(DomainEvent):
    """
    Evento emitido cuando se crea una competición.

    Este evento representa el nacimiento de un nuevo torneo en el sistema.
    Otros módulos pueden escucharlo para inicializar configuraciones relacionadas.

    Atributos:
        competition_id: ID de la competición creada (str UUID)
        creator_id: ID del usuario que creó el torneo (str UUID)
        name: Nombre del torneo
    """

    competition_id: str
    creator_id: str
    name: str
