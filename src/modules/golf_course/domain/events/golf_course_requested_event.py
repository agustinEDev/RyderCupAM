"""
GolfCourseRequestedEvent - Creator solicita un nuevo campo de golf.
"""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class GolfCourseRequestedEvent(DomainEvent):
    """
    Evento de dominio: Creator solicita un nuevo campo de golf.

    Se dispara cuando un Creator crea una solicitud de campo de golf
    que entra en estado PENDING_APPROVAL.

    Trigger: Email a Admin notificando nueva solicitud pendiente.

    Atributos:
        golf_course_id: ID del campo solicitado (str UUID)
        golf_course_name: Nombre del campo
        creator_id: ID del usuario que solicitó el campo (str UUID)
    """

    golf_course_id: str
    golf_course_name: str
    creator_id: str
