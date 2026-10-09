"""OrdenDeSalida Value Object - Quién sale primero al generar las partidas (#251)."""

from enum import StrEnum


class OrdenDeSalida(StrEnum):
    """
    - HIGH_FIRST: Los hándicaps más altos salen primero
    - LOW_FIRST: Los más bajos salen primero
    """

    HIGH_FIRST = "HIGH_FIRST"
    LOW_FIRST = "LOW_FIRST"

    def __str__(self) -> str:
        return self.value
