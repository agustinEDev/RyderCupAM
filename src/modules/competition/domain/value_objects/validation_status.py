"""
ValidationStatus Value Object - Estado de validacion cruzada de un score.
"""

from enum import StrEnum


class ValidationStatus(StrEnum):
    """
    Estado de validacion cruzada entre jugador y marcador.

    - PENDING: Falta el score del jugador o del marcador (o ambos)
    - MATCH: Ambos scores coinciden (incluido None == None para picked up)
    - MISMATCH: Los scores difieren (incluido None vs numero)
    """

    PENDING = "PENDING"
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"

    def __str__(self) -> str:
        return self.value
