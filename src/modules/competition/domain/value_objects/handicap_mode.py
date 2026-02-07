"""
HandicapMode Value Object - Modo de handicap para Singles.
"""

from enum import StrEnum


class HandicapMode(StrEnum):
    """
    Modo de cálculo de handicap para partidos Singles.

    - MATCH_PLAY: Allowance recomendado 100% (Ryder Cup siempre es match play)

    Este enum solo aplica para formato SINGLES.
    FOURBALL y FOURSOMES tienen sus propios cálculos fijos.
    """

    MATCH_PLAY = "MATCH_PLAY"

    def default_allowance(self) -> int:
        """Retorna el allowance por defecto según WHS."""
        return 100  # MATCH_PLAY

    def __str__(self) -> str:
        return self.value
