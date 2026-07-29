"""
QuickMatchHoleScoreId Value Object - Identificador unico de un score de hoyo.
"""

import uuid
from dataclasses import dataclass


class InvalidQuickMatchHoleScoreIdError(Exception):
    """Excepcion lanzada cuando un QuickMatchHoleScoreId no es valido."""

    pass


@dataclass(frozen=True)
class QuickMatchHoleScoreId:
    """Value Object para identificadores unicos de score de hoyo de una partida rapida."""

    value: uuid.UUID

    def __init__(self, value: uuid.UUID | str):
        val = None
        if isinstance(value, uuid.UUID):
            val = value
        elif isinstance(value, str):
            try:
                val = uuid.UUID(value)
            except ValueError as e:
                raise InvalidQuickMatchHoleScoreIdError(
                    f"'{value}' no es un string UUID valido"
                ) from e
        else:
            raise InvalidQuickMatchHoleScoreIdError(
                f"Se esperaba un UUID o un string, pero se recibio {type(value).__name__}"
            )

        object.__setattr__(self, "value", val)

    @classmethod
    def generate(cls) -> "QuickMatchHoleScoreId":
        return cls(uuid.uuid4())

    def __str__(self) -> str:
        return str(self.value)

    def __eq__(self, other) -> bool:
        return isinstance(other, QuickMatchHoleScoreId) and self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)
