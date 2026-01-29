"""
CourseType Value Object - Tipo de campo de golf.
"""

from enum import Enum


class CourseType(str, Enum):
    """
    Tipos de campos de golf soportados.

    - STANDARD_18: Campo estándar de 18 hoyos (par 66-76)
    - PITCH_AND_PUTT: Campo corto con hoyos par 3
    - EXECUTIVE: Campo ejecutivo con mix de par 3 y par 4
    """

    STANDARD_18 = "STANDARD_18"
    PITCH_AND_PUTT = "PITCH_AND_PUTT"
    EXECUTIVE = "EXECUTIVE"

    def __str__(self) -> str:
        return self.value
