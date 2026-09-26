"""
MatchFormat Value Object - Formato de partido.
"""

from enum import StrEnum


class MatchFormat(StrEnum):
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

    def one_ball_per_side(self) -> bool:
        """Si cada bando juega UNA sola bola, a golpes alternos (foursomes).

        Entonces la bola, sus golpes y su tarjeta son del bando, no de cada
        jugador (decidido en agosto; tarjetas, BE #377).
        """
        return self == MatchFormat.FOURSOMES

    def __str__(self) -> str:
        return self.value
