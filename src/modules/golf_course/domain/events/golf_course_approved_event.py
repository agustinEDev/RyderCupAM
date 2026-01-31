"""
GolfCourseApprovedEvent - Admin aprueba un campo de golf.
"""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class GolfCourseApprovedEvent(DomainEvent):
    """
    Evento de dominio: Admin aprueba un campo de golf.

    Se dispara cuando un Admin aprueba una solicitud de campo,
    cambiando el estado de PENDING_APPROVAL → APPROVED.

    Trigger: Email bilingüe (ES/EN) al Creator notificando aprobación.

    Atributos:
        golf_course_id: ID del campo aprobado (str UUID)
        golf_course_name: Nombre del campo
        creator_id: ID del usuario creador (str UUID)
    """

    golf_course_id: str
    golf_course_name: str
    creator_id: str
