"""
ScoringFormat Value Object - Cómo se puntúa un stroke play individual.

Vive en `shared` (RyderCupAM#165): lo usan la partida rápida (partido libre, de
1 a 4 jugadores, todos contra todos) y lo usará la competición stroke play
(#251). Es la pareja de `MatchFormat`, que es el formato de match play: cada uno
sabe su porcentaje WHS por defecto.
"""

from enum import StrEnum

# Estándar WHS del stroke play individual
STROKE_PLAY_INDIVIDUAL_ALLOWANCE = 95


class ScoringFormat(StrEnum):
    """
    Formato de puntuacion en un partido libre de QuickMatch.

    - MEDAL: stroke play, gana quien menos golpes netos totaliza.
    - STABLEFORD: por puntos, gana quien mas puntos totaliza.
    """

    MEDAL = "MEDAL"
    STABLEFORD = "STABLEFORD"

    @property
    def default_allowance(self) -> int:
        """
        Porcentaje WHS por defecto: 95%, el estándar del stroke play individual,
        para Medal y para Stableford. Antes era la constante FREE_PLAY_ALLOWANCE
        de la partida rápida (RyderCupAM#165).
        """
        return STROKE_PLAY_INDIVIDUAL_ALLOWANCE

    def __str__(self) -> str:
        return self.value
