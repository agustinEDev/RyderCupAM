# src/modules/user/domain/value_objects/user_id.py
import uuid
from dataclasses import dataclass


class InvalidUserIdError(Exception):
    """Excepción lanzada cuando un UserId no es válido."""

    pass


@dataclass(frozen=True)
class UserId:
    """
    Value Object para identificadores únicos de usuario.
    Almacena internamente un objeto UUID, garantizando siempre un estado válido.
    """

    value: uuid.UUID

    def __init__(self, value: uuid.UUID | str):
        """
        Constructor que acepta tanto un objeto UUID como un string UUID.
        Esto proporciona flexibilidad al crear instancias.
        """
        val = None
        if isinstance(value, uuid.UUID):
            val = value
        elif isinstance(value, str):
            try:
                val = uuid.UUID(value)
            except ValueError as e:
                raise InvalidUserIdError(f"'{value}' no es un string UUID válido") from e
        else:
            raise InvalidUserIdError(
                f"Se esperaba un UUID o un string, pero se recibió {type(value)}"
            )

        # Usar object.__setattr__ porque la clase es frozen
        object.__setattr__(self, "value", val)

    @classmethod
    def generate(cls) -> "UserId":
        """Genera un nuevo UserId con un UUID v4 aleatorio."""
        return cls(uuid.uuid4())

    def __str__(self) -> str:
        """Representación string del UUID."""
        return str(self.value)

    def __eq__(self, other) -> bool:
        """Operador de igualdad."""
        return isinstance(other, UserId) and self.value == other.value

    def __lt__(self, other) -> bool:
        """Operador menor que (para ordenamiento)."""
        if not isinstance(other, UserId):
            return NotImplemented
        return self.value < other.value

    def __hash__(self) -> int:
        """Hash del UserId para uso en sets y dicts."""
        return hash(self.value)
