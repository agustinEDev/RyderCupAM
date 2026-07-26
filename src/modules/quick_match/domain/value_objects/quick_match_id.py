"""
QuickMatchId Value Object - Identificador unico de una partida rapida.

Este Value Object representa la identidad de una QuickMatch usando UUID.
"""

import uuid
from dataclasses import dataclass


class InvalidQuickMatchIdError(Exception):
    """Excepcion lanzada cuando un QuickMatchId no es valido."""

    pass


@dataclass(frozen=True)
class QuickMatchId:
    """
    Value Object para identificadores unicos de partida rapida.

    Almacena internamente un objeto UUID, garantizando siempre un estado valido.
    Inmutable y validado automaticamente.
    """

    value: uuid.UUID

    def __init__(self, value: uuid.UUID | str):
        val = None
        if isinstance(value, uuid.UUID):
            val = value
        elif isinstance(value, str):
            try:
                val = uuid.UUID(value)
            except ValueError as e:
                raise InvalidQuickMatchIdError(f"'{value}' no es un string UUID valido") from e
        else:
            raise InvalidQuickMatchIdError(
                f"Se esperaba un UUID o un string, pero se recibio {type(value).__name__}"
            )

        object.__setattr__(self, "value", val)

    @classmethod
    def generate(cls) -> "QuickMatchId":
        """Genera un nuevo QuickMatchId con un UUID v4 aleatorio."""
        return cls(uuid.uuid4())

    def __str__(self) -> str:
        return str(self.value)

    def __eq__(self, other) -> bool:
        return isinstance(other, QuickMatchId) and self.value == other.value

    def __lt__(self, other) -> bool:
        if not isinstance(other, QuickMatchId):
            return NotImplemented
        return self.value < other.value

    def __hash__(self) -> int:
        return hash(self.value)
