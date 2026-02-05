"""
MatchFormat Value Object - Formato de partido.
"""

from enum import Enum


class MatchFormat(str, Enum):
    """
    Formatos de partido en competiciones Ryder Cup.

    - SINGLES: 1 vs 1 (un jugador por equipo)
    - FOURBALL: 2 vs 2, cada jugador juega su bola (mejor bola del equipo)
    - FOURSOMES: 2 vs 2, golpes alternados con una bola por equipo
    """

    SINGLES = "SINGLES"
    FOURBALL = "FOURBALL"
    FOURSOMES = "FOURSOMES"

    def players_per_team(self) -> int:
        """Retorna el número de jugadores por equipo según el formato."""
        if self == MatchFormat.SINGLES:
            return 1
        return 2  # FOURBALL y FOURSOMES

    def __str__(self) -> str:
        return self.value
