"""
ApprovalStatus Value Object - Estado de aprobación de campos de golf.

Workflow:
- PENDING_APPROVAL: Creator crea solicitud
- APPROVED: Admin aprueba (campo disponible para todos)
- REJECTED: Admin rechaza (solo visible para Admin + owner)
"""

from enum import Enum, StrEnum


class ApprovalStatus(StrEnum):
    """
    Estados de aprobación para GolfCourse.

    Workflow inmutable:
    PENDING_APPROVAL → APPROVED (final)
    PENDING_APPROVAL → REJECTED (final)

    Ver ADR-032 para detalles.
    """

    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

    def __str__(self) -> str:
        return self.value

    def is_pending(self) -> bool:
        """Retorna True si está pendiente de aprobación."""
        return self == ApprovalStatus.PENDING_APPROVAL

    def is_approved(self) -> bool:
        """Retorna True si fue aprobado."""
        return self == ApprovalStatus.APPROVED

    def is_rejected(self) -> bool:
        """Retorna True si fue rechazado."""
        return self == ApprovalStatus.REJECTED

    def is_final(self) -> bool:
        """Retorna True si está en estado final (APPROVED o REJECTED)."""
        return self in [ApprovalStatus.APPROVED, ApprovalStatus.REJECTED]
