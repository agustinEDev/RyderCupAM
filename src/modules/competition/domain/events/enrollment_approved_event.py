# -*- coding: utf-8 -*-
"""
EnrollmentApprovedEvent - Se emite cuando se aprueba una inscripción.
"""

from dataclasses import dataclass
from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class EnrollmentApprovedEvent(DomainEvent):
    """
    Evento emitido cuando se aprueba una inscripción.

    Puede ser:
    - Aprobación de solicitud (REQUESTED → APPROVED)
    - Aceptación de invitación (INVITED → APPROVED)
    - Inscripción directa por creador (→ APPROVED)

    Otros módulos pueden:
    - Notificar al jugador
    - Actualizar contadores de participantes
    - Inicializar datos del jugador para el torneo

    Atributos:
        enrollment_id: ID de la inscripción (str UUID)
        competition_id: ID de la competición (str UUID)
        user_id: ID del jugador (str UUID)
    """

    enrollment_id: str
    competition_id: str
    user_id: str
