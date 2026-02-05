"""
PlayMode Value Object - Modo de juego de una competición.
"""

from enum import Enum


class PlayMode(str, Enum):
    """
    Modo de juego del torneo.

    - SCRATCH: Sin handicap, todos juegan igual. Para jugadores de nivel similar.
    - HANDICAP: Se aplica el sistema de handicaps WHS con allowances configurables.
    """

    SCRATCH = "SCRATCH"
    HANDICAP = "HANDICAP"

    def allows_handicap(self) -> bool:
        """Retorna True si el modo permite usar handicaps."""
        return self == PlayMode.HANDICAP

    def __str__(self) -> str:
        return self.value
