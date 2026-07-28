"""
ScoringFormat Value Object - Formato de puntuacion de una partida rapida libre.

Local a `quick_match`: a diferencia de `match_format` (compartido con
`competition`, siempre por equipos a match play), este formato es exclusivo
del modo "partido libre" (1 a 4 jugadores, todos contra todos, sin equipos).
"""

from enum import StrEnum


class ScoringFormat(StrEnum):
    """
    Formato de puntuacion en un partido libre de QuickMatch.

    - MEDAL: stroke play, gana quien menos golpes netos totaliza.
    - STABLEFORD: por puntos, gana quien mas puntos totaliza.
    """

    MEDAL = "MEDAL"
    STABLEFORD = "STABLEFORD"

    def __str__(self) -> str:
        return self.value
