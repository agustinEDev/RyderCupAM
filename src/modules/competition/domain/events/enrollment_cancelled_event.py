# -*- coding: utf-8 -*-
"""
EnrollmentCancelledEvent - Se emite cuando un jugador cancela su solicitud/invitación.
"""

from dataclasses import dataclass
from typing import Optional
from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class EnrollmentCancelledEvent(DomainEvent):
    """
    Evento emitido cuando un jugador cancela su solicitud o declina una invitación.

    Diferencia con WITHDRAWN:
    - CANCELLED: El jugador cancela antes de estar inscrito (desde REQUESTED o INVITED)
    - WITHDRAWN: El jugador se retira después de estar inscrito (desde APPROVED)

    Otros módulos pueden:
    - Notificar al creador si es una solicitud cancelada
    - Actualizar métricas de interés en el torneo
    - Limpiar datos temporales

    Atributos:
        enrollment_id: ID de la inscripción (str UUID)
        competition_id: ID de la competición (str UUID)
        user_id: ID del jugador (str UUID)
        reason: Razón de la cancelación (opcional)
    """

    enrollment_id: str
    competition_id: str
    user_id: str
    reason: Optional[str] = None
