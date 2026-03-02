"""
MatchStatus Value Object - Estado de un partido.
"""

from enum import StrEnum


class MatchStatus(StrEnum):
    """
    Estados del ciclo de vida de un partido.

    - SCHEDULED: Programado, pendiente de iniciar
    - IN_PROGRESS: En curso
    - COMPLETED: Finalizado normalmente
    - WALKOVER: Finalizado por incomparecencia (victoria por WO)
    - CONCEDED: Finalizado por concesion de un equipo
    """

    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    WALKOVER = "WALKOVER"
    CONCEDED = "CONCEDED"

    def is_finished(self) -> bool:
        """Retorna True si el partido ha terminado."""
        return self in {MatchStatus.COMPLETED, MatchStatus.WALKOVER, MatchStatus.CONCEDED}

    def can_start(self) -> bool:
        """Retorna True si el partido puede iniciarse."""
        return self == MatchStatus.SCHEDULED

    def can_record_scores(self) -> bool:
        """Retorna True si se pueden registrar scores."""
        return self == MatchStatus.IN_PROGRESS

    def can_concede(self) -> bool:
        """Retorna True si el partido puede ser concedido."""
        return self == MatchStatus.IN_PROGRESS

    def __str__(self) -> str:
        return self.value
