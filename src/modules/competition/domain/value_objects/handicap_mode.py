"""
HandicapMode Value Object - Modo de handicap para Singles.
"""

from enum import StrEnum


class HandicapMode(StrEnum):
    """
    Modo de cálculo de handicap para partidos Singles.

    - MATCH_PLAY: Ryder Cup siempre es match play. Su porcentaje por defecto (100%)
      lo da MatchFormat.SINGLES.default_allowance (RyderCupAM#165)

    Este enum solo aplica para formato SINGLES.
    FOURBALL y FOURSOMES tienen sus propios cálculos fijos.
    """

    MATCH_PLAY = "MATCH_PLAY"

    def __str__(self) -> str:
        return self.value
