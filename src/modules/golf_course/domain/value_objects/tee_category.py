"""
TeeCategory Value Object - Categoría normalizada de tees.

Permite cálculo consistente de Playing Handicap según WHS.
"""

from enum import Enum


class TeeCategory(str, Enum):
    """
    Categorías normalizadas de tees para Playing Handicap (WHS).

    - CHAMPIONSHIP_MALE: Tees campeonato masculino (máxima dificultad)
    - AMATEUR_MALE: Tees amateur masculino (estándar)
    - FORWARD_MALE: Tees adelantados masculino
    - CHAMPIONSHIP_FEMALE: Tees campeonato femenino
    - AMATEUR_FEMALE: Tees amateur femenino (estándar)
    - FORWARD_FEMALE: Tees adelantados femenino

    Cada tee tiene slope_rating y course_rating para cálculo de PH.
    Ver ADR-023 para detalles sobre Playing Handicap WHS.
    """

    CHAMPIONSHIP_MALE = "CHAMPIONSHIP_MALE"
    AMATEUR_MALE = "AMATEUR_MALE"
    FORWARD_MALE = "FORWARD_MALE"
    CHAMPIONSHIP_FEMALE = "CHAMPIONSHIP_FEMALE"
    AMATEUR_FEMALE = "AMATEUR_FEMALE"
    FORWARD_FEMALE = "FORWARD_FEMALE"

    def __str__(self) -> str:
        return self.value
