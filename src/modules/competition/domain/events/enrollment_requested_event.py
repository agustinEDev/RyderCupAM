"""
EnrollmentRequestedEvent - Se emite cuando un jugador solicita unirse.
"""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class EnrollmentRequestedEvent(DomainEvent):
    """
    Evento emitido cuando un jugador solicita inscribirse en un torneo.

    Otros módulos pueden:
    - Notificar al creador del torneo
    - Registrar la solicitud para auditoría

    Atributos:
        enrollment_id: ID de la inscripción (str UUID)
        competition_id: ID de la competición (str UUID)
        user_id: ID del jugador que solicita (str UUID)
    """

    enrollment_id: str
    competition_id: str
    user_id: str
