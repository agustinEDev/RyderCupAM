"""
DraftStatus Value Object - En qué punto está la sala de draft (FE #653).

PENDING: la sala existe y espera a que el organizador lance el sorteo.
IN_PROGRESS: hay turno, hay reloj y se elige.
COMPLETED: no queda nadie por elegir; de ahí salen los equipos.

No hay «cancelada»: si el organizador no quiere draft, reparte los equipos a
mano y la sala no llega a empezar.
"""

from enum import StrEnum


class DraftStatus(StrEnum):
    """En qué punto está la sala."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"

    def __str__(self) -> str:
        return self.value
