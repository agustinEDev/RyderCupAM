"""Draft ID Value Object - Identificador de una sala de draft (FE #653)."""

from uuid import UUID, uuid4


class DraftId:
    """Value Object para el ID de una sala de draft."""

    def __init__(self, value: UUID | str):
        """
        Inicializa el ID.

        Args:
            value: UUID o string representando el ID

        Raises:
            ValueError: Si el valor no es un UUID válido
        """
        if isinstance(value, str):
            try:
                self._value = UUID(value)
            except ValueError as e:
                raise ValueError(f"Invalid UUID format: {value}") from e
        elif isinstance(value, UUID):
            self._value = value
        else:
            raise ValueError(f"DraftId must be UUID or str, got {type(value)}")

    @property
    def value(self) -> UUID:
        """Retorna el UUID subyacente."""
        return self._value

    @classmethod
    def generate(cls) -> "DraftId":
        """Genera un nuevo ID único."""
        return cls(uuid4())

    def __eq__(self, other: object) -> bool:
        return isinstance(other, DraftId) and self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __str__(self) -> str:
        return str(self._value)

    def __repr__(self) -> str:
        return f"DraftId({self._value})"
