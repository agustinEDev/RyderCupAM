"""
Round ID Value Object.

Identificador único para cada ronda de competición.
"""

from uuid import UUID, uuid4


class RoundId:
    """
    Value Object para el ID de una ronda.

    Responsabilidades:
    - Encapsular el UUID de la ronda
    - Validar que sea un UUID válido
    - Generar nuevos IDs únicos

    Características:
    - Inmutable (no se puede modificar después de crear)
    - Se compara por valor (equality by value)
    - Lightweight (solo encapsula un UUID)
    """

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
            raise ValueError(f"RoundId must be UUID or str, got {type(value)}")

    @property
    def value(self) -> UUID:
        """Retorna el UUID subyacente."""
        return self._value

    @classmethod
    def generate(cls) -> "RoundId":
        """
        Genera un nuevo ID único.

        Returns:
            RoundId con UUID v4 aleatorio
        """
        return cls(uuid4())

    def __eq__(self, other: object) -> bool:
        """Compara por valor (equality by value)."""
        if not isinstance(other, RoundId):
            return False
        return self._value == other._value

    def __lt__(self, other: "RoundId") -> bool:
        """Less than comparison for sorting."""
        if not isinstance(other, RoundId):
            return NotImplemented
        return self._value < other._value

    def __le__(self, other: "RoundId") -> bool:
        """Less than or equal comparison."""
        if not isinstance(other, RoundId):
            return NotImplemented
        return self._value <= other._value

    def __gt__(self, other: "RoundId") -> bool:
        """Greater than comparison."""
        if not isinstance(other, RoundId):
            return NotImplemented
        return self._value > other._value

    def __ge__(self, other: "RoundId") -> bool:
        """Greater than or equal comparison."""
        if not isinstance(other, RoundId):
            return NotImplemented
        return self._value >= other._value

    def __hash__(self) -> int:
        """Permite usar en sets y como dict key."""
        return hash(self._value)

    def __str__(self) -> str:
        """Representación en string (para logs, debug)."""
        return str(self._value)

    def __repr__(self) -> str:
        """Representación técnica (para debugging)."""
        return f"RoundId({self._value!r})"
