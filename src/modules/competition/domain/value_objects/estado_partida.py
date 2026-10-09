"""EstadoPartida Value Object - En qué punto está una partida de stroke play (#251)."""

from enum import StrEnum


class EstadoPartida(StrEnum):
    """
    - SCHEDULED: Generada, todavía no ha salido
    - IN_PROGRESS: En el campo
    - COMPLETED: Acabada
    """

    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"

    def empezada(self) -> bool:
        """Si ya salió: a partir de ahí no se toca (D1, D2, D11)."""
        return self != EstadoPartida.SCHEDULED

    def __str__(self) -> str:
        return self.value
