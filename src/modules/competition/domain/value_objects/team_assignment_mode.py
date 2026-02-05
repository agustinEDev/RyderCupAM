"""
TeamAssignmentMode Value Object - Modo de asignación de equipos.
"""

from enum import StrEnum


class TeamAssignmentMode(StrEnum):
    """
    Modos de asignación de jugadores a equipos.

    - AUTOMATIC: Snake draft automático por handicap
    - MANUAL: Asignación manual por el creador
    """

    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"

    def __str__(self) -> str:
        return self.value
