"""
GolfCourseRejectedEvent - Admin rechaza un campo de golf.
"""

from datetime import datetime

from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.events.domain_event import DomainEvent

from ..value_objects.golf_course_id import GolfCourseId


class GolfCourseRejectedEvent(DomainEvent):
    """
    Evento de dominio: Admin rechaza un campo de golf.

    Se dispara cuando un Admin rechaza una solicitud de campo,
    cambiando el estado de PENDING_APPROVAL → REJECTED.

    Trigger: Email bilingüe (ES/EN) al Creator notificando rechazo con razón.
    """

    def __init__(
        self,
        golf_course_id: GolfCourseId,
        golf_course_name: str,
        creator_id: UserId,
        rejection_reason: str,
        occurred_on: datetime | None = None,
    ) -> None:
        super().__init__(occurred_on)
        self.golf_course_id = golf_course_id
        self.golf_course_name = golf_course_name
        self.creator_id = creator_id
        self.rejection_reason = rejection_reason

    def __repr__(self) -> str:
        return (
            f"GolfCourseRejectedEvent("
            f"golf_course_id={self.golf_course_id}, "
            f"name={self.golf_course_name}, "
            f"creator_id={self.creator_id}, "
            f"reason={self.rejection_reason[:50]}..., "
            f"occurred_on={self.occurred_on})"
        )
