"""
TeeCategory Value Object - Categoría normalizada de tees por dificultad.

El género se gestiona por separado en el campo `gender` de cada Tee.
"""

from enum import StrEnum


class TeeCategory(StrEnum):
    """
    Categorías normalizadas de tees por nivel de dificultad (WHS).

    - CHAMPIONSHIP: Tees campeonato (máxima dificultad)
    - AMATEUR: Tees amateur (estándar)
    - SENIOR: Tees senior
    - FORWARD: Tees adelantados (menor distancia)
    - JUNIOR: Tees para jugadores junior

    Cada tee tiene slope_rating y course_rating para cálculo de PH.
    El género (MALE/FEMALE/None) se almacena como campo separado en Tee.
    """

    CHAMPIONSHIP = "CHAMPIONSHIP"
    AMATEUR = "AMATEUR"
    SENIOR = "SENIOR"
    FORWARD = "FORWARD"
    JUNIOR = "JUNIOR"

    def __str__(self) -> str:
        return self.value
