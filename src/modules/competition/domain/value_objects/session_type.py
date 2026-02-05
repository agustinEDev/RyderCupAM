"""
SessionType Value Object - Tipo de sesión en una jornada.
"""

from enum import Enum


class SessionType(str, Enum):
    """
    Tipos de sesión en un día de competición.

    - MORNING: Sesión de mañana
    - AFTERNOON: Sesión de tarde
    - EVENING: Sesión nocturna (campos con luz)

    Reglas:
    - Máximo 3 sesiones por día (una de cada tipo)
    - No puede haber duplicados del mismo tipo el mismo día
    """

    MORNING = "MORNING"
    AFTERNOON = "AFTERNOON"
    EVENING = "EVENING"

    def __str__(self) -> str:
        return self.value
