"""
TeamAssignment Value Object - Tipo de asignación de equipos en una competición.

Define cómo se asignan los jugadores a los equipos en un torneo formato Ryder Cup.
"""

from enum import StrEnum
from typing import Any


class TeamAssignment(StrEnum):
    """
    Enum para los tipos de asignación de equipos.

    Tipos:
    - MANUAL: El creador asigna manualmente los jugadores a cada equipo
    - AUTOMATIC: El sistema asigna automáticamente (por hándicap, aleatoriamente, etc.)

    Ejemplos:
        >>> assignment = TeamAssignment.MANUAL
        >>> assignment.value
        'MANUAL'

        >>> TeamAssignment("AUTOMATIC")
        <TeamAssignment.AUTOMATIC: 'AUTOMATIC'>
    """

    MANUAL = "MANUAL"
    AUTOMATIC = "AUTOMATIC"

    def __composite_values__(self) -> tuple[Any, ...]:
        """
        Retorna los valores para SQLAlchemy composite mapping.

        Requerido para que SQLAlchemy pueda persistir el Value Object.
        """
        return (self.value,)
