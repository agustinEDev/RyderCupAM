"""
TeamAssignmentMode Value Object - Modo de asignación de equipos.
"""

from enum import StrEnum


class TeamAssignmentMode(StrEnum):
    """
    Modos de asignación de jugadores a equipos.

    - AUTOMATIC: Snake draft automático por handicap
    - MANUAL: Asignación manual por el creador
    - DRAFT: Los eligieron los capitanes en la sala de draft (FE #653)

    DRAFT no se puede pedir: no es una forma de repartir que el organizador
    dispare, es lo que queda cuando la sala termina. Quien lo pida por la API de
    reparto se lleva un error, porque si no el reparto automático se guardaría
    diciendo que lo eligieron los capitanes.
    """

    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"
    DRAFT = "DRAFT"

    def __str__(self) -> str:
        return self.value
