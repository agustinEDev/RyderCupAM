"""
ScheduleConfigMode Value Object - Modo de configuración del calendario.
"""

from enum import StrEnum


class ScheduleConfigMode(StrEnum):
    """
    Modos de configuración del calendario de rondas.

    - AUTOMATIC: Genera rondas automáticamente según número de sesiones
    - MANUAL: El creador define cada ronda manualmente
    """

    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"

    def __str__(self) -> str:
        return self.value
