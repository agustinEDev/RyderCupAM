"""
CompetitionUpdatedEvent - Se emite cuando se actualiza la información del torneo.
"""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class CompetitionUpdatedEvent(DomainEvent):
    """
    Evento emitido cuando se actualiza la configuración del torneo.

    Solo se emite cuando el torneo está en DRAFT.
    Otros módulos pueden:
    - Actualizar caches
    - Notificar a usuarios interesados sobre cambios
    - Actualizar vistas materializadas

    Atributos:
        competition_id: ID de la competición (str UUID)
        name: Nombre del torneo (puede haber cambiado)
    """

    competition_id: str
    name: str
