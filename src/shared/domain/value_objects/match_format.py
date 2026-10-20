"""
MatchFormat Value Object - Formato de partido de match play.

Vive en `shared` porque es del golf, no de las competiciones: lo usan la
competición y la partida rápida (RyderCupAM#165). Antes la partida rápida lo
importaba del módulo de competición.
"""

from enum import StrEnum


class MatchFormat(StrEnum):
    """
    Formatos de partido de match play, en competición y en partida rápida.

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

    @property
    def default_allowance(self) -> int:
        """
        Porcentaje WHS por defecto del formato (RyderCupAM#165).

        Vivía dos veces, en `Round` y en `QuickMatch`, cada uno con sus
        constantes y su método: ahora lo sabe el propio formato.

        - SINGLES: 100%
        - FOURBALL: 90%
        - FOURSOMES: 50%, aplicado a la DIFERENCIA entre los dos bandos
        """
        return _DEFAULT_ALLOWANCE[self]

    def __str__(self) -> str:
        return self.value


_DEFAULT_ALLOWANCE: dict[MatchFormat, int] = {
    MatchFormat.SINGLES: 100,
    MatchFormat.FOURBALL: 90,
    MatchFormat.FOURSOMES: 50,
}
