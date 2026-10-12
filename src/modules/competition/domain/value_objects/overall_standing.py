"""
OverallStanding Value Object - Cómo se calcula la general de un stroke play (RyderCupAM#251).

La elige el organizador (decisión 7 de la #251, confirmada el 6 oct 2026): con
gente jugando días distintos no hay una única respuesta buena.
"""

from enum import StrEnum


class OverallStanding(StrEnum):
    """Qué cuenta de cada jugador en la clasificación general."""

    # Stableford: suma de puntos de todas sus tarjetas. Medal: suma de golpes netos
    ACCUMULATED = "ACCUMULATED"
    # La mejor de sus tarjetas
    BEST_CARD = "BEST_CARD"

    def __str__(self) -> str:
        return self.value
