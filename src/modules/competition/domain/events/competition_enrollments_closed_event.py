# -*- coding: utf-8 -*-
"""
CompetitionEnrollmentsClosedEvent - Se emite cuando se cierran las inscripciones.
"""

from dataclasses import dataclass
from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class CompetitionEnrollmentsClosedEvent(DomainEvent):
    """
    Evento emitido cuando se cierran las inscripciones de una competición.

    Indica que ya no se aceptan más jugadores.
    Otros módulos pueden:
    - Notificar a jugadores aprobados
    - Rechazar solicitudes pendientes
    - Iniciar proceso de asignación de equipos

    Atributos:
        competition_id: ID de la competición (str UUID)
        total_enrollments: Número total de inscripciones aprobadas
    """

    competition_id: str
    total_enrollments: int
