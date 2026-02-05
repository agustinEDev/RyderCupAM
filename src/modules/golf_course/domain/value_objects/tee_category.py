"""
TeeCategory Value Object - Categoría normalizada de tees.

Permite cálculo consistente de Playing Handicap según WHS.
"""

from enum import StrEnum


class TeeCategory(StrEnum):
    """
    Categorías normalizadas de tees para Playing Handicap (WHS).

    - CHAMPIONSHIP_MALE: Tees campeonato masculino (máxima dificultad)
    - AMATEUR_MALE: Tees amateur masculino (estándar)
    - SENIOR_MALE: Tees senior masculino
    - CHAMPIONSHIP_FEMALE: Tees campeonato femenino
    - AMATEUR_FEMALE: Tees amateur femenino (estándar)
    - SENIOR_FEMALE: Tees senior femenino
    - JUNIOR: Tees para jugadores junior

    Cada tee tiene slope_rating y course_rating para cálculo de PH.
    Ver ADR-023 para detalles sobre Playing Handicap WHS.
    """

    CHAMPIONSHIP_MALE = "CHAMPIONSHIP_MALE"
    AMATEUR_MALE = "AMATEUR_MALE"
    SENIOR_MALE = "SENIOR_MALE"
    CHAMPIONSHIP_FEMALE = "CHAMPIONSHIP_FEMALE"
    AMATEUR_FEMALE = "AMATEUR_FEMALE"
    SENIOR_FEMALE = "SENIOR_FEMALE"
    JUNIOR = "JUNIOR"

    def __str__(self) -> str:
        return self.value
