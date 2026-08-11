"""Value Object: identificador de una foto de la galeria."""

import uuid
from dataclasses import dataclass


class InvalidProfilePhotoIdError(Exception):
    """El identificador de foto no es valido."""


@dataclass(frozen=True)
class ProfilePhotoId:
    """Identificador unico de una foto del perfil."""

    value: uuid.UUID

    def __init__(self, value: uuid.UUID | str):
        if isinstance(value, uuid.UUID):
            val = value
        elif isinstance(value, str):
            try:
                val = uuid.UUID(value)
            except ValueError as error:
                raise InvalidProfilePhotoIdError(f"'{value}' no es un UUID valido") from error
        else:
            raise InvalidProfilePhotoIdError(
                f"Se esperaba un UUID o un string, se recibio {type(value)}"
            )

        object.__setattr__(self, "value", val)

    @classmethod
    def generate(cls) -> "ProfilePhotoId":
        return cls(uuid.uuid4())

    def __str__(self) -> str:
        return str(self.value)
