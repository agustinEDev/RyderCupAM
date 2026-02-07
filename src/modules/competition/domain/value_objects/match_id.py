"""
Match ID Value Object.

Identificador único para cada partido de una ronda.
"""

from uuid import UUID, uuid4


class MatchId:
    """
    Value Object para el ID de un partido.

    Responsabilidades:
    - Encapsular el UUID del partido
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
            raise ValueError(f"MatchId must be UUID or str, got {type(value)}")

    @property
    def value(self) -> UUID:
        """Retorna el UUID subyacente."""
        return self._value

    @classmethod
    def generate(cls) -> "MatchId":
        """
        Genera un nuevo ID único.

        Returns:
            MatchId con UUID v4 aleatorio
        """
        return cls(uuid4())

    def __eq__(self, other: object) -> bool:
        """Compara por valor (equality by value)."""
        if not isinstance(other, MatchId):
            return False
        return self._value == other._value

    def __lt__(self, other: "MatchId") -> bool:
        """Less than comparison for sorting."""
        if not isinstance(other, MatchId):
            return NotImplemented
        return self._value < other._value

    def __le__(self, other: "MatchId") -> bool:
        """Less than or equal comparison."""
        if not isinstance(other, MatchId):
            return NotImplemented
        return self._value <= other._value

    def __gt__(self, other: "MatchId") -> bool:
        """Greater than comparison."""
        if not isinstance(other, MatchId):
            return NotImplemented
        return self._value > other._value

    def __ge__(self, other: "MatchId") -> bool:
        """Greater than or equal comparison."""
        if not isinstance(other, MatchId):
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
        return f"MatchId({self._value!r})"
