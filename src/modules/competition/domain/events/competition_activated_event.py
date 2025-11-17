# -*- coding: utf-8 -*-
"""
CompetitionActivatedEvent - Se emite cuando una competición pasa de DRAFT a ACTIVE.
"""

from dataclasses import dataclass
from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class CompetitionActivatedEvent(DomainEvent):
    """
    Evento emitido cuando se activa una competición.

    Indica que el torneo está listo y acepta inscripciones.
    Otros módulos pueden:
    - Enviar notificaciones a usuarios interesados
    - Publicar en redes sociales
    - Inicializar sistemas de inscripción

    Atributos:
        competition_id: ID de la competición activada (str UUID)
        name: Nombre del torneo
        start_date: Fecha de inicio (ISO format string)
    """

    competition_id: str
    name: str
    start_date: str  # ISO format date
