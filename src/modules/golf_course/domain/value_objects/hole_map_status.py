"""
HoleMapStatus Value Object - Estado de revisión del mapa de un recorrido.

Workflow (BE #532; desde el 18 oct lo importado entra aprobado):
- APPROVED: lo ven los jugadores; lo importado de OSM nace así, sin revisor, y
  reimportar lo deja así
- PENDING_REVIEW: importado antes del 18 oct, nadie lo ha mirado; no se enseña
- REJECTED: un admin lo descartó; una reimportación lo deja aprobado
"""

from enum import StrEnum


class HoleMapStatus(StrEnum):
    """Estados de revisión de CourseHoleMap."""

    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

    def __str__(self) -> str:
        return self.value
