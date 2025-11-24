# -*- coding: utf-8 -*-
"""
EnrollmentWithdrawnEvent - Se emite cuando un jugador se retira.
"""

from dataclasses import dataclass
from typing import Optional
from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class EnrollmentWithdrawnEvent(DomainEvent):
    """
    Evento emitido cuando un jugador se retira voluntariamente.

    Otros módulos pueden:
    - Notificar al creador del torneo
    - Actualizar contadores
    - Reasignar equipos si ya estaba asignado

    Atributos:
        enrollment_id: ID de la inscripción (str UUID)
        competition_id: ID de la competición (str UUID)
        user_id: ID del jugador (str UUID)
        reason: Razón del retiro (opcional)
    """

    enrollment_id: str
    competition_id: str
    user_id: str
    reason: Optional[str] = None
