"""
RoundStatus Value Object - Estado de una ronda.
"""

from enum import Enum


class RoundStatus(str, Enum):
    """
    Estados del ciclo de vida de una ronda.

    - PENDING_TEAMS: Esperando asignación de equipos
    - PENDING_MATCHES: Equipos asignados, esperando generación de partidos
    - SCHEDULED: Partidos generados, lista para jugar
    - IN_PROGRESS: Ronda en curso (al menos un partido iniciado)
    - COMPLETED: Todos los partidos finalizados
    """

    PENDING_TEAMS = "PENDING_TEAMS"
    PENDING_MATCHES = "PENDING_MATCHES"
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"

    def can_generate_matches(self) -> bool:
        """Retorna True si se pueden generar partidos."""
        return self == RoundStatus.PENDING_MATCHES

    def can_modify(self) -> bool:
        """Retorna True si la ronda puede modificarse."""
        return self in {RoundStatus.PENDING_TEAMS, RoundStatus.PENDING_MATCHES}

    def is_finished(self) -> bool:
        """Retorna True si la ronda ha terminado."""
        return self == RoundStatus.COMPLETED

    def __str__(self) -> str:
        return self.value
