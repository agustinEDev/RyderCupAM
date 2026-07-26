"""
ParticipantId Value Object - Identificador unico de un participante de partida rapida.

Comun a participantes registrados (coincide con su UserId) e invitados
(generado, sin cuenta de usuario asociada).
"""

import uuid
from dataclasses import dataclass


class InvalidParticipantIdError(Exception):
    """Excepcion lanzada cuando un ParticipantId no es valido."""

    pass


@dataclass(frozen=True)
class ParticipantId:
    """Value Object para identificadores unicos de participante."""

    value: uuid.UUID

    def __init__(self, value: uuid.UUID | str):
        val = None
        if isinstance(value, uuid.UUID):
            val = value
        elif isinstance(value, str):
            try:
                val = uuid.UUID(value)
            except ValueError as e:
                raise InvalidParticipantIdError(f"'{value}' no es un string UUID valido") from e
        else:
            raise InvalidParticipantIdError(
                f"Se esperaba un UUID o un string, pero se recibio {type(value).__name__}"
            )

        object.__setattr__(self, "value", val)

    @classmethod
    def generate(cls) -> "ParticipantId":
        return cls(uuid.uuid4())

    def __str__(self) -> str:
        return str(self.value)

    def __eq__(self, other) -> bool:
        return isinstance(other, ParticipantId) and self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)
