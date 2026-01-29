"""
GolfCourseRejectedEvent - Admin rechaza un campo de golf.
"""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class GolfCourseRejectedEvent(DomainEvent):
    """
    Evento de dominio: Admin rechaza un campo de golf.

    Se dispara cuando un Admin rechaza una solicitud de campo,
    cambiando el estado de PENDING_APPROVAL → REJECTED.

    Trigger: Email bilingüe (ES/EN) al Creator notificando rechazo con razón.

    Atributos:
        golf_course_id: ID del campo rechazado (str UUID)
        golf_course_name: Nombre del campo
        creator_id: ID del usuario creador (str UUID)
        rejection_reason: Razón del rechazo
    """

    golf_course_id: str
    golf_course_name: str
    creator_id: str
    rejection_reason: str
