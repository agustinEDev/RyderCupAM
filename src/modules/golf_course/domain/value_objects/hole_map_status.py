"""
HoleMapStatus Value Object - Estado de revisión del mapa de un recorrido.

Workflow (BE #532):
- PENDING_REVIEW: importado, nadie lo ha mirado; no se enseña a los jugadores
- APPROVED: un admin lo dio por bueno
- REJECTED: un admin lo descartó; una reimportación lo devuelve a pendiente
"""

from enum import StrEnum


class HoleMapStatus(StrEnum):
    """Estados de revisión de CourseHoleMap."""

    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

    def __str__(self) -> str:
        return self.value
