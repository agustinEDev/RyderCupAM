"""
HandicapMode Value Object - Modo de handicap para Singles.
"""

from enum import Enum, StrEnum


class HandicapMode(StrEnum):
    """
    Modo de cálculo de handicap para partidos Singles.

    - STROKE_PLAY: Allowance recomendado 95%
    - MATCH_PLAY: Allowance recomendado 100%

    Este enum solo aplica para formato SINGLES.
    FOURBALL y FOURSOMES tienen sus propios cálculos fijos.
    """

    STROKE_PLAY = "STROKE_PLAY"
    MATCH_PLAY = "MATCH_PLAY"

    def default_allowance(self) -> int:
        """Retorna el allowance por defecto según WHS."""
        if self == HandicapMode.STROKE_PLAY:
            return 95
        return 100  # MATCH_PLAY

    def __str__(self) -> str:
        return self.value
